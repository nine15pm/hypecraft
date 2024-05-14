import promptconfigs
import requests
import json
import utils

#CONFIGS
##############################################################################################
#Summary configs
MAX_POSTS_PER_STORY_SUMMARY = 3

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
    utils.countTokensAndSave(inputs)
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
def classifyPost(post, feed, prompt_config='default') -> str:
    prompt_config = promptconfigs.CLASSIFIER_PROMPTS['categorize'] if prompt_config == 'default' else prompt_config
    feed_source = 'Source type: ' + feed['feed_source']
    feed_name = 'Source name: ' + feed['feed_name'] + '\n'
    headline = 'Post headline: ' + post['post_title'] + '\n'
    post_tags = ('Post tags: ' + post['post_tags'][0] + '\n') if post['post_tags'] is not None else ''
    external_link = ('Linked site: ' + post['external_link'] + '\n') if post['external_link'] is not None else ''
    content = feed_source + feed_name + headline + post_tags + external_link
    return getResponseLLAMA(content, prompt_config).strip('#')

#SUMMARIZATION
##############################################################################################

#construct the prompt for post and get summary
def generateNewsPostSummary(post, feed, prompt_config='default') -> str:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['news'] if prompt_config == 'default' else prompt_config
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
def mapNewsPostsToStories(posts: list, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.COLLATION_PROMPTS['group_headlines_news'] if prompt_config == 'default' else prompt_config
    content = ''
    #construct the string listing all headlines
    for post in posts:
        content = content + '{"hid": ' + str(post['post_id']) + ', "h": "' + post['post_title'] + '"}\n'
    model_response = getResponseLLAMA(content, prompt_config)
    try:
        output = json.loads(model_response)
        return output
    except:
        print('Initial story mapping from model not valid JSON, trying fix...')
    try:
        model_response = fixJSON(model_response)
        output = json.loads(model_response)
        return output
    except Exception as error:
        print(f'Story mapping error:', type(error).__name__, "-", error)
        print(model_response)
        raise error

#collates posts associated with story into a single summary
def generateStorySummary(storyposts: list, topic_name: str, prompt_config='default') -> tuple[str, list]:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['story_summary_news_fn'](topic_name) if prompt_config == 'default' else prompt_config
    content = ''
    #check if there is only 1 post
    if len(storyposts) == 1:
        #if just 1, then return existing summary
        summary = storyposts[0]['summary_ml']
        posts_summarized = [storyposts[0]['post_id']]
    else:
        #if more than 1 post, but within cap of 3, then use all posts for summary
        if len(storyposts) <= MAX_POSTS_PER_STORY_SUMMARY:
            selected_posts = storyposts
        
        #if more than max cap of 3 posts, then select the newest, longest text, highest likes score, in that order
        else:
            selected_posts = []
            #get list index and post for newest post
            filtered = max(enumerate(storyposts), key = lambda post: post[1]['post_publish_time'])
            del storyposts[filtered[0]]
            selected_posts.append(filtered[1])
            #out of remaining posts, get longest text post
            filtered = max(enumerate(storyposts), key = lambda post: len((post[1]['post_text'] if post[1]['post_text'] is not None else '') + post[1]['external_parsed_text']))
            del storyposts[filtered[0]]
            selected_posts.append(filtered[1])
            #out of remaining posts, get most likes post
            filtered = max(enumerate(storyposts), key = lambda post: post[1]['likes_score'])
            del storyposts[filtered[0]]
            selected_posts.append(filtered[1])

        #construct content string for model
        for i, post in enumerate(selected_posts):
            post_string = f'Post {i} headline: {post['post_title']}\n\
                Post {i} text: {post['summary_ml']}\n\n'
            content = content + post_string
        #generate summary
        summary = getResponseLLAMA(content, prompt_config)
        posts_summarized = [post['post_id'] for post in selected_posts]
    return summary, posts_summarized

#write an overall summary for the topic by combining all the top stories
def generateTopicSummary(stories: list, prompt_config='default') -> str:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['topic_summary_news'] if prompt_config == 'default' else prompt_config
    #construct string combining all story summaries
    content = ''
    for idx, story in enumerate(stories):
        story_summary = 'Story ' + str(idx) + ": \n" + story['summary_ml'] + '\n\n'
        content = content + story_summary
    return getResponseLLAMA(content, prompt_config)

#HEADLINE GENERATION
##############################################################################################
#write the headline for a story
def generateHeadlineFromSummary(summary, prompt_config='default') -> str:
    prompt_config = promptconfigs.HEADLINE_PROMPTS['news_headline'] if prompt_config == 'default' else prompt_config
    return getResponseLLAMA(summary, prompt_config)

#RANKING AND SELECTION
##############################################################################################
#For a given set of stories, return scores reflecting the importance
def scoreNewsStories(stories: list, topic_name: str, prompt_config='default') -> list:
    prompt_config = promptconfigs.RANKING_PROMPTS['score_headlines_news'](topic_name) if prompt_config == 'default' else prompt_config
    content = ''
    for story in stories:
        content = content + '{"hid": ' + str(story['story_id']) + ', "h": "' + story['headline_ml'] + '"}\n'
    model_response = getResponseLLAMA(content, prompt_config)
    try:
        output = json.loads(model_response)
        return output
    except:
        print('Initial story scoring output not valid JSON, trying fix...')
    try:
        model_response = fixJSON(model_response)
        output = json.loads(model_response)
        return output
    except Exception as error:
        print(f'Story scoring error:', type(error).__name__, "-", error)
        print(model_response)
        raise

#ERROR FIXING
##############################################################################################
def fixJSON(JSON_string: str, prompt_config='default') -> str:
    prompt_config = promptconfigs.ERROR_FIXING_PROMPTS['fix_JSON'] if prompt_config == 'default' else prompt_config
    return getResponseLLAMA(JSON_string, prompt_config)