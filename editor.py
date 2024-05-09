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
def classifyPost(post, feed, prompt_config) -> str:
    feed_source = 'Source type: ' + feed['feed_source']
    feed_name = 'Source name: ' + feed['feed_name'] + '\n'
    headline = 'Post headline: ' + post['post_title'] + '\n'
    post_tags = ('Post tags: ' + post['post_tags'][0] + '\n') if post['post_tags'] is not None else ''
    external_link = ('Linked site: ' + post['external_link'] + '\n') if post['external_link'] is not None else ''
    content = feed_source + feed_name + headline + post_tags + external_link
    return getResponseLLAMA(content, prompt_config).strip('#')

#SUMMARIZATION
##############################################################################################

#construct the prompt for Reddit post and get summary
def generateNewsPostSummary(post, feed, prompt_config) -> str:
    #combine post data into chunk of text for model
    feed_source = 'Source type: ' + feed['feed_source']
    feed_name = 'Source name: ' + feed['feed_name'] + '\n'
    headline = 'Post headline: ' + post['post_title'] + '\n'
    post_text = 'Post text: ' + post['post_text'] + '\n' if post['post_text'] is not None else ''
    external_link = ('Linked site: ' + post['external_link'] + '\n') if post['external_link'] is not None else ''
    external_text = ('Linked site text: ' + post['external_parsed_text'] + '\n') if post['external_parsed_text'] is not None else ''
    content = feed_source + feed_name + headline + post_text + external_link + external_text
    return getResponseLLAMA(content, prompt_config)

#STORY COLLATION
##############################################################################################

#Groups similar/repeat headlines into stories
def mapNewsPostsToStories(posts: list, prompt_config) -> list[dict]:
    content = ''
    #construct the string listing all headlines
    for idx, post in enumerate(posts):
        content = content + '{"hid": ' + str(post['post_id']) + ', "h": "' + post['post_title'] + '"}\n'
    model_response = getResponseLLAMA(content, prompt_config)
    try:
        output = json.loads(model_response)
        return output
    except ValueError:
        print("Story grouping output from model is not valid JSON")
        print(model_response)

#collates posts associated with story into a single summary
def generateStorySummary(storyposts: list, prompt_config) -> tuple[str, list]:
    #get story posts and check if there is only 1 post
    if len(storyposts) == 1:
        #if just 1, then return existing summary
        return storyposts[0]['summary_ml'], [storyposts[0]['post_id']]
    #otherwise, take most upvoted post and newest post and combine these into 1 summary
    else:
        #get newest post
        newest = max(storyposts, key = lambda post: post['post_publish_time'])
        #get most upvoted post >>>>>>>>>> (REFACTOR THIS LOGIC LATER TO MAKE NON-REDDIT SPECIFIC) <<<<<<<<<<<
        most_liked = max(storyposts, key = lambda post: post['likes_score'])
        #assemble content strings for model
        newest_headline = 'Post 1 headline: ' + newest['post_title'] + '\n'
        newest_text = 'Post 1 text:' + newest['summary_ml'] + '\n'
        most_liked_headline = 'Post 2 headline: ' + most_liked['post_title'] + '\n'
        most_liked_text = 'Post 2 text: ' + most_liked['summary_ml'] + '\n'
        content = newest_headline + newest_text + most_liked_headline + most_liked_text
        return getResponseLLAMA(content, prompt_config), [newest['post_id'], most_liked['post_id']]

#write an overall summary for the topic by combining all the top stories
def generateTopicSummary(stories: list, prompt_config) -> str:
    #construct string combining all story summaries
    content = ''
    for idx, story in enumerate(stories):
        story_summary = 'Story ' + str(idx) + ": \n" + story['summary_ml'] + '\n\n'
        content = content + story_summary
    return getResponseLLAMA(content, prompt_config)