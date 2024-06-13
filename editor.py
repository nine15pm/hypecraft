import promptconfigs
import requests
import json
import utils
from datetime import datetime
from openai import OpenAI

#CONFIGS
##############################################################################################
#Summary configs
MAX_POSTS_PER_STORY_SUMMARY = 4
NUM_WORDS_POST_EXCERPT = 100

#Huggingface API
HF_API_URL = 'https://api-inference.huggingface.co/models/'
HF_API_KEY = utils.read_secrets('HF_API_KEY')
HF_API_HEADERS = {
    'Authorization': f'Bearer {HF_API_KEY}'
    }
HF_MODEL = 'meta-llama/Meta-Llama-3-70B-Instruct'

#OpenAI API
OPENAI_API_KEY = utils.read_secrets('OPENAI_API_KEY')
OPENAI_MODEL = 'gpt-4o'

#CALL MODELS
##############################################################################################
#General function to call LLAMA3 with correctly assembled prompt and get response
def getResponseLLAMA(content: str, prompt_config: dict, prior_chat: list[dict] = None, return_user_prompt = False):
    params = prompt_config['model_params']
    user_prompt = prompt_config['user_prompt'] + content
    inputs = promptconfigs.constructPromptLLAMA(user_prompt=user_prompt, prior_chat=prior_chat, system_prompt=prompt_config['system_prompt'])
    utils.countTokensAndSaveLlama3(inputs)
    payload = {
        'inputs': inputs,
        'parameters': params,
        'options': {
            'wait_for_model': True
        }
    }
    response = requests.post(HF_API_URL + HF_MODEL, headers=HF_API_HEADERS, json=payload)
    try:
        output = response.json()[0]['generated_text']
        return (output, user_prompt) if return_user_prompt else output
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
        print(response.json())
        raise

def getResponseOPENAI(content: str, prompt_config: dict, prior_chat: list[dict] = None, return_user_prompt = False):
    client = OpenAI(api_key=OPENAI_API_KEY)
    params = prompt_config['model_params']
    user_prompt = prompt_config['user_prompt'] + content
    messages = promptconfigs.constructPromptOPENAI(user_prompt=user_prompt, prior_chat=prior_chat, system_prompt=prompt_config['system_prompt'])
    response = client.chat.completions.create(
        model = OPENAI_MODEL,
        messages=messages,
        max_tokens = params['max_new_tokens'],
        temperature = params['temperature'],
        top_p = params['top_p']
    )
    output = response.choices[0].message.content
    utils.countTokensAndSaveOAI(response.usage.prompt_tokens, response.usage.completion_tokens)
    return (output, user_prompt) if return_user_prompt else output

#PARSING RESPONSE
##############################################################################################
def extractResponseJSON(response, step_label='[unspecified step]'):
    try:
        json_extracted = utils.parseMapping(response)
    except:
        print(f'Cannot extract out JSON from {step_label}...')
        print(response)
        raise
    try:
        output = json.loads(json_extracted)
        return output
    except:
        print('Extracted JSON is not valid, trying fix...')
    try:
        json_extracted = fixJSON(json_extracted)
        output = json.loads(json_extracted)
        return output
    except Exception as error:
        print(f'{step_label} error:', type(error).__name__, "-", error)
        print(response)
        raise error

#CLASSIFICATION
##############################################################################################
#construct the prompt for Reddit post and get category
def classifyPost(post, feed, prompt_config='default') -> str:
    prompt_config = promptconfigs.CLASSIFIER_PROMPTS['categorize'] if prompt_config == 'default' else prompt_config
    feed_source = 'Source type: ' + feed['feed_source']
    feed_name = 'Source name: ' + feed['feed_name'] + '\n'
    headline = 'Post title: ' + post['post_title'] + '\n'
    post_tags = ('Post tags: ' + post['post_tags'][0] + '\n') if post['post_tags'] is not None else ''
    post_text = ('Post text: ' + post['post_text'] + '\n') if post['post_text'] is not None else ''
    external_link = ('Linked site: ' + post['external_link'] + '\n') if post['external_link'] is not None else ''
    external_link_text = ('Linked site text: ' + post['external_parsed_text'] + '\n') if post['external_parsed_text'] is not None else ''
    content_long = feed_source + feed_name + headline + post_tags + post_text + external_link + external_link_text
    content_short = feed_source + feed_name + headline + post_tags + external_link_text
    
    if utils.tokenCountLlama3(content_long) <= prompt_config['model_params']['truncate']:
        content = content_long
    else:
        content = content_short

    return getResponseLLAMA(content, prompt_config).strip('#')

#SUMMARIZATION
##############################################################################################

#construct the prompt for post and get summary
def generateNewsPostSummary(post, feed, topic_prompt_params: dict, prompt_config='default') -> str:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['post_summary_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    #combine post data into chunk of text for model
    feed_source = 'Source type: ' + feed['feed_source']
    feed_name = 'Source name: ' + feed['feed_name'] + '\n'
    headline = 'Post headline: ' + post['post_title'] + '\n'
    post_text = 'Post text: ' + post['post_text'] + '\n' if post['post_text'] is not None else ''
    external_link = ('Linked site: ' + post['external_link'] + '\n') if post['external_link'] is not None else ''
    external_text = ('Linked site text: ' + post['external_parsed_text'] + '\n') if post['external_parsed_text'] is not None else ''
    content = feed_source + feed_name + headline + post_text + external_link + external_text
    return getResponseLLAMA(content, prompt_config)

#NEWS FILTERING AND COLLATION
##############################################################################################
#Filter out outdated news stories
def filterOutdatedNews(posts: list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.FILTERING_PROMPTS['filter_outdated_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''
    for post in posts:
        content = content + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'
    
    response = getResponseOPENAI(content, prompt_config)
    
    print(response)
    return extractResponseJSON(response, step_label = 'filter outdated news')

#Brainstorm and collect a set of potential theme options
def brainstormNewsThemes(posts: list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.COLLATION_PROMPTS['brainstorm_theme_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''

    #construct the string with all the posts
    for post in posts:
        content = content + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'

    #check if tokens exceeds max input, if so, just use titles no summary text
    #content = content_long if utils.tokenCountLlama3(content_long) <= prompt_config_init['model_params']['truncate'] else content_short

    #first get initial themes from model with base prompt
    response = getResponseLLAMA(content, prompt_config)
    return extractResponseJSON(response, step_label = 'brainstorm themes')

#Select the best fit themes to bucket news posts from the brainstormed options
def selectNewsThemes(posts: list, theme_options:list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.COLLATION_PROMPTS['select_theme_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''

    #add theme options to string
    content = content + f'SECTION OPTIONS: \n\n{json.dumps(theme_options)} \n\nNEWS POSTS: \n\n'

    #construct the string with all the posts
    for post in posts:
        content = content + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'

    #check if tokens exceeds max input, if so, just use titles no summary text
    #content = content_long if utils.tokenCountLlama3(content_long) <= prompt_config_init['model_params']['truncate'] else content_short

    #first get initial themes from model with base prompt
    response = getResponseOPENAI(content, prompt_config)

    print(response)
    return extractResponseJSON(response, step_label = 'select themes')

#Groups news posts into up to N buckets
def assignNewsPostsToThemes(posts: list, themes: list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    themes_str = json.dumps(themes)
    print(themes_str)
    prompt_config = promptconfigs.COLLATION_PROMPTS['assign_theme_news_fn'](themes_str, topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''
    #construct the string with all the posts
    for post in posts:
        content = content+ f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'

    #check if tokens exceeds max input, if so, just use titles no summary text
    #content = content_long if utils.tokenCountLlama3(content_long) <= prompt_config_init['model_params']['truncate'] else content_short

    response = getResponseOPENAI(content, prompt_config)

    print(response)
    return extractResponseJSON(response, step_label = 'map posts to themes')

#Groups similar/repeat headlines into stories - split into 2 steps, initial and revise
def groupNewsPostsToStories(posts: list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.COLLATION_PROMPTS['group_story_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''

    #construct the string with all the posts
    for post in posts:
        content = content + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'

    #check if tokens exceeds max input, if so, just use titles no summary text
    #content = content_long if utils.tokenCountLlama3(content_long) <= prompt_config_init['model_params']['truncate'] else content_short

    response = getResponseOPENAI(content, prompt_config)
    return extractResponseJSON(response, step_label = 'group posts to stories')

#Filters RAG results to remove unrelated stories
def filterStoryRAGResults(target_story: dict, RAG_stories: list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.FILTERING_PROMPTS['filter_RAG_results_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''

    #add target story to string
    content = content + f'TARGET POST: \n\nHeadline:{target_story['headline_ml']} \nSummary: {target_story['summary_ml']}\n\n'

    #add RAG story to string
    for story in RAG_stories:
        content = content + f'CANDIDATE POSTS: \n\n{{"id": {story['story_id']}, "headline": {story['headline_ml']}}}\n'
    
    response = getResponseLLAMA(content, prompt_config)

    return extractResponseJSON(response, step_label = 'filter RAG results')

#filter based on whether story has meaningful new info vs. past stories discussing the same news
def filterStoryNewInfo(target_story: dict, past_stories: list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.FILTERING_PROMPTS['filter_newinfo_story_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''

    #add target story to string
    content = content + f'TARGET POST: \n\nHeadline:{target_story['headline_ml']} \nSummary: {target_story['summary_ml']}\n\n'

    #add past stories to string
    for story in past_stories:
        content = content + f'PAST POSTS: \n\n{{"id": {story['story_id']}, "headline": {story['headline_ml']}}}\n'
    
    response = getResponseLLAMA(content, prompt_config)
    return extractResponseJSON(response, step_label = 'filter if story has new info vs past')

#collates posts associated with story into a single summary
def generateStorySummary(storyposts: list, topic_prompt_params: dict, prompt_config='default') -> tuple[str, list]:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['story_summary_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''
    #check if there is only 1 post
    if len(storyposts) == 1:
        #if just 1, then return existing summary
        summary = storyposts[0]['summary_ml']
        posts_summarized = [storyposts[0]['post_id']]
    else:
        #if more than 1 post, but within cap, then use all posts for summary
        if len(storyposts) <= MAX_POSTS_PER_STORY_SUMMARY:
            selected_posts = storyposts
        
        #if more than max cap posts, then select the newest, longest text, highest likes score, in that order
        else:
            selected_posts = []
            #get list index and post for newest post
            filtered = sorted(enumerate(storyposts), key = lambda post: post[1]['post_publish_time'], reverse=True)
            del storyposts[filtered[0][0]]
            selected_posts.append(filtered[0][1])
            #out of remaining posts, get 2 longest text posts
            filtered = sorted(enumerate(storyposts), key = lambda post: len((post[1]['post_text'] if post[1]['post_text'] is not None else '') + (post[1]['external_parsed_text'] if post[1]['external_parsed_text'] is not None else '')), reverse=True)
            del storyposts[filtered[0][0]]
            del storyposts[filtered[1][0]]
            selected_posts.append(filtered[0][1])
            selected_posts.append(filtered[1][1])
            #out of remaining posts, get most likes post
            filtered = sorted(enumerate(storyposts), key = lambda post: (post[1]['likes_score'] if post[1]['likes_score'] is not None else 0), reverse=True)
            del storyposts[filtered[0][0]]
            selected_posts.append(filtered[0][1])

        #construct content string for model
        for i, post in enumerate(selected_posts):
            post_string = f'Post {i} headline: {post['retitle_ml']}\n\
                Post {i} text: {post['summary_ml']}\n\n'
            content = content + post_string
        #generate summary
        response = getResponseLLAMA(content, prompt_config)
        summary = extractResponseJSON(response, step_label = 'story summarization')[0]['summary']
        posts_summarized = [post['post_id'] for post in selected_posts]
    return summary, posts_summarized

def rewriteStorySummaryPastContext(story, past_stories: list, topic_prompt_params: dict, prompt_config='default') -> str:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['story_rewrite_summary_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''

    #add current story
    content += f'DRAFT SUMMARY:\n\nDate: {datetime.strftime(story['created_at'], "%A, %B %m")}\nHeadline: {story['headline_ml']}\nText: {story['summary_ml']}\n\n'
    
    #add past stories
    content += 'PAST POSTS:\n\n'
    for i, past_story in enumerate(past_stories):
        content += f'Post {i} date: {datetime.strftime(past_story['created_at'], "%A, %B %m")}\nPost {i} headline: {past_story['headline_ml']}\nPost {i} text: {past_story['summary_ml']}\n\n'
    
    response = getResponseLLAMA(content, prompt_config)
    summary = extractResponseJSON(response, step_label = 'rewrite story summary w past context')[0]['summary']
    return summary

#write a short summary of the remaining non-top news organized by theme
def generateRadarSummary(stories: list, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['theme_summary_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    #construct string combining all story summaries
    content = ''
    for story in stories:
        story_str = f'{{"story_id": {story['story_id']}, "i_score": {story['daily_i_score_ml']}), "text": {story['summary_ml']}}}\n'
        content = content + story_str
    
    response = getResponseLLAMA(content, prompt_config)
    summary_phrase_list = extractResponseJSON(response, step_label = 'rewrite story summary w past context')
    return summary_phrase_list

#write a set of highlight bullets for the topic
def generateTopicSummary(stories: list, topic_prompt_params: dict, prompt_config='default') -> str:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['topic_summary_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    #construct string combining all story summaries
    content = ''
    for story in stories:
        story_str = f'[story_id: {story['story_id']}] {story['summary_ml']} \n\n'
        content = content + story_str
    response = getResponseLLAMA(content, prompt_config)

    return extractResponseJSON(response, step_label = 'generate topic summary bullets')

#HEADLINE GENERATION
##############################################################################################
#factually retitle a post for higher quality post title
def retitleNewsPost(post_summary, prompt_config='default') -> str:
    prompt_config = promptconfigs.HEADLINE_PROMPTS['news_post_retitle'] if prompt_config == 'default' else prompt_config
    return getResponseLLAMA(post_summary, prompt_config)

#write the headline for a story
def generateHeadlineFromSummary(summary, prompt_config='default') -> str:
    prompt_config = promptconfigs.HEADLINE_PROMPTS['news_headline'] if prompt_config == 'default' else prompt_config
    return getResponseLLAMA(summary, prompt_config)

#RANKING AND SELECTION
##############################################################################################
#For a given set of stories, return scores reflecting the importance
def scoreNewsStories(stories: list, topic_prompt_params: dict, prompt_config='default') -> list:
    prompt_config = promptconfigs.RANKING_PROMPTS['score_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''
    for story in stories:
        content = content + f'{{"sid": {story['story_id']}, "headline": "{story['headline_ml']}", "summary": "{story['summary_ml']}"}}\n'
    
    response = getResponseOPENAI(content, prompt_config)
    return extractResponseJSON(response, step_label = 'story ranking')

#generate 3 tweet search queries for calcing trend score
def generateTweetSearchQueries(story: dict, topic_prompt_params: dict, prompt_config='default') -> list[dict]:
    prompt_config = promptconfigs.RANKING_PROMPTS['tweet_search_query_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = f'Headline: {story['headline_ml']} \nSummary: {story['summary_ml']}'
    response = getResponseLLAMA(content, prompt_config)
    return extractResponseJSON(response, step_label = 'generate tweet search query')

#ERROR FIXING
##############################################################################################
def fixJSON(JSON_string: str, prompt_config='default') -> str:
    prompt_config = promptconfigs.ERROR_FIXING_PROMPTS['fix_JSON'] if prompt_config == 'default' else prompt_config
    return getResponseLLAMA(JSON_string, prompt_config)