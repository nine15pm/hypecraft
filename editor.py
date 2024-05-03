import promptconfigs
import requests

#CONFIGS
##############################################################################################
#File paths
PATH_POSTS_REDDIT = 'posts_reddit.json'
PATH_POSTS_SUBSTACK = 'posts_substack.json'

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
def getResponseLLAMA(content, prompt_config, print=False):
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
def classifyReddit(reddit_post, prompt_config):
    source = 'Source: Reddit'
    subreddit = 'Subreddit: ' + reddit_post['subreddit'] + '\n'
    headline = 'Reddit post headline: ' + reddit_post['headline'] + '\n'
    post_flair = 'Post flair: ' + reddit_post['post_flair'] + '\n' if reddit_post['post_flair'] is not None else ''
    external_link = 'Linked site: ' + reddit_post['external_content_link'] + '\n' if reddit_post['external_content_link'] is not None else ''
    content = source + subreddit + headline + post_flair + external_link
    return getResponseLLAMA(content, prompt_config).strip('#')

#SUMMARIZATION
##############################################################################################

#construct the prompt for Reddit post and get summary
def generateSummariesReddit(reddit_post, prompt_config):
    #combine post data into chunk of text for model
    headline = 'Reddit post headline: ' + reddit_post['headline'] + '\n'
    post_text = 'Reddit post text: ' + reddit_post['post_text'] + '\n' if reddit_post['post_text'] is not None else ''
    external_link = 'Linked site: ' + reddit_post['external_content_link'] + '\n' if reddit_post['external_content_link'] is not None else ''
    external_text = 'Linked site text: ' + reddit_post['external_scraped_text'] + '\n' if reddit_post['external_scraped_text'] is not None else ''
    content = headline + post_text + external_link + external_text
    return getResponseLLAMA(content, prompt_config)

#STORY COLLATION
##############################################################################################

#parse headlines and group repeats into a story
def parseStories(headlines, prompt_config):
    content = ''
    return getResponseLLAMA(content, prompt_config)

#group headlines into story
#collate summaries for story into single summary