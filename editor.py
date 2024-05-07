import promptconfigs
import requests
import json
import utils
from datetime import date

#CONFIGS
##############################################################################################
#File paths
subreddit = 'formula1'
PATH_POSTS_REDDIT = 'data/posts_reddit_' + subreddit + "_" + date.today().strftime('%m-%d') + '.json'

#Huggingface API
HF_API_URL = 'https://api-inference.huggingface.co/models/'
HF_API_KEY = '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'
HF_API_HEADERS = {
    'Authorization': f'Bearer {HF_API_KEY}'
    }
HF_MODEL = promptconfigs.DEFAULT_MODEL

#CALL MODEL
##############################################################################################
#General function to call model with correctly assembled prompt and get response
def getResponseLLAMA(content, prompt_config, print=False) -> str:
    params = prompt_config['model_params']
    user_prompt = prompt_config['user_prompt'] + content
    inputs = promptconfigs.constructPromptLLAMA(user_prompt=user_prompt, system_prompt=prompt_config['system_prompt'])
    payload = {
        'inputs': inputs,
        'parameters': params
    }
    response = requests.post(HF_API_URL + HF_MODEL, headers=HF_API_HEADERS, json=payload)
    if print:
        print(response.json()[0]['generated_text'])
    return response.json()[0]['generated_text']

#CLASSIFICATION
##############################################################################################
#construct the prompt for Reddit post and get category
def classifyPost(post, prompt_config) -> str:
    source_type = 'Source type: ' + post['source_name']
    source_name = 'Source name: ' + post['source_type'] + '\n'
    headline = 'Post headline: ' + post['headline'] + '\n'
    post_tags = ('Post tags: ' + post['post_tags'] + '\n') if post['post_tags'] is not None else ''
    external_link = ('Linked site: ' + post['external_content_link'] + '\n') if post['external_content_link'] is not None else ''
    content = source_type + source_name + headline + post_tags + external_link
    return getResponseLLAMA(content, prompt_config).strip('#')

#SUMMARIZATION
##############################################################################################

#construct the prompt for Reddit post and get summary
def generatePostSummary(post, prompt_config) -> str:
    #combine post data into chunk of text for model
    source_type = 'Source type: ' + post['source_name']
    source_name = 'Source name: ' + post['source_type'] + '\n'
    headline = 'Post headline: ' + post['headline'] + '\n'
    post_text = 'Post text: ' + post['post_text'] + '\n' if post['post_text'] is not None else ''
    external_link = ('Linked site: ' + post['external_content_link'] + '\n') if post['external_content_link'] is not None else ''
    external_text = ('Linked site text: ' + post['external_scraped_text'] + '\n') if post['external_scraped_text'] is not None else ''
    content = source_type + source_name + headline + post_text + external_link + external_text
    return getResponseLLAMA(content, prompt_config)

#STORY COLLATION
##############################################################################################

#Groups similar/repeat headlines into stories
def groupPostHeadlines(posts, prompt_config) -> dict:
    content = ''
    #construct the string listing all headlines
    for idx, post in enumerate(posts):
        content = content + '{"hid": ' + str(idx) + ', "h": "' + post['headline'] + '"}\n'
    print(content)
    model_response = getResponseLLAMA(content, prompt_config)
    try:
        output = json.loads(model_response)
        return output
    except ValueError:
        print("Story grouping output from model is not valid JSON")
        print(model_response)

def getPostsForStory(story) -> list[dict]:
    story_post_ids = story['hid']
    posts = [post for post in utils.loadJSON(PATH_POSTS_REDDIT) if post['category_ml'] == 'news'] #REFACTOR THIS LATER SINCE THIS IS SPECIFIC TO NEWS IN ORDER TO GET RIGHT ID
    output = []
    for id in story_post_ids:
        output.append(posts[id])
    return output

#collates posts associated with story into a single summary
def generateStorySummary(storyposts, prompt_config) -> tuple[str, list]:
    #get story posts and check if there is only 1 post
    if len(storyposts) == 1:
        #if just 1, then return existing summary
        return storyposts[0]['summary_ml'], [0]
    #otherwise, take most upvoted post and newest post and combine these into 1 summary
    else:
        #get newest post
        newest_idx, newest = max(enumerate(storyposts), key = lambda post: post[1]['publish_time'])
        #get most upvoted post >>>>>>>>>> (REFACTOR THIS LOGIC LATER TO MAKE NON-REDDIT SPECIFIC) <<<<<<<<<<<
        most_upvoted_idx, most_upvoted = max(enumerate(storyposts), key = lambda post: post[1]['vote_score'])
        #assemble content strings for model
        newest_headline = 'Post 1 headline: ' + newest['headline'] + '\n'
        newest_text = 'Post 1 text:' + newest['summary_ml'] + '\n'
        most_upvoted_headline = 'Post 2 headline: ' + most_upvoted['headline'] + '\n'
        most_upvoted_text = 'Post 2 text: ' + most_upvoted['summary_ml'] + '\n'
        content = newest_headline + newest_text + most_upvoted_headline + most_upvoted_text
        return getResponseLLAMA(content, prompt_config), [newest_idx, most_upvoted_idx]

#write an overall summary for the topic by combining all the top stories
def generateTopicSummary(stories, prompt_config) -> str:
    #construct string combining all story summaries
    content = ''
    for idx, story in enumerate(stories):
        story_summary = 'Story ' + str(idx) + ": \n" + story['summary_ml'] + '\n\n'
        content = content + story_summary
    return getResponseLLAMA(content, prompt_config)