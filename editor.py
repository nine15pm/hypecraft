import promptconfigs
import requests
import json
import utils

#CONFIGS
##############################################################################################
#Summary configs
MAX_POSTS_PER_STORY_SUMMARY = 3
NUM_WORDS_POST_EXCERPT = 100

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
def getResponseLLAMA(content: str, prompt_config: dict, prior_chat: list[dict] = None, return_user_prompt = False):
    params = prompt_config['model_params']
    user_prompt = prompt_config['user_prompt'] + content
    inputs = promptconfigs.constructPromptLLAMA(user_prompt=user_prompt, prior_chat=prior_chat, system_prompt=prompt_config['system_prompt'])
    utils.countTokensAndSave(inputs)
    payload = {
        'inputs': inputs,
        'parameters': params
    }
    response = requests.post(HF_API_URL + HF_MODEL, headers=HF_API_HEADERS, json=payload)
    try:
        output = response.json()[0]['generated_text']
        return (output, user_prompt) if return_user_prompt else output
    except Exception as error:
        print("Error:", type(error).__name__, "-", error)
        print(response.json())
        raise

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

#Come up with themes to bucket news posts
def draftNewsThemes(posts: list, topic_prompt_params: dict, prompt_config_init='default', prompt_config_revise='default') -> list[dict]:
    prompt_config_init = promptconfigs.COLLATION_PROMPTS['draft_theme_news_fn'](topic_prompt_params) if prompt_config_init == 'default' else prompt_config_init
    prompt_config_revise = promptconfigs.COLLATION_PROMPTS['draft_theme_news_revise_fn'](topic_prompt_params) if prompt_config_revise == 'default' else prompt_config_revise
    content_long = ''
    content_short = ''

    #construct the string with all the posts
    for post in posts:
        content_long = content_long + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'
        content_short = content_short + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}"}}\n'
    
    #check if tokens exceeds max input, if so, just use titles no summary text
    content = content_short
    #content = content_long if utils.tokenCountLlama3(content_long) <= prompt_config_init['model_params']['truncate'] else content_short

    #first get initial themes from model with base prompt
    initial_response, user_prompt = getResponseLLAMA(content, prompt_config_init, return_user_prompt=True)

    print(initial_response)

    #then send model chat history and ask it to revise
    prior_chat = [{
        'user': user_prompt,
        'assistant': initial_response
    }]
    revised_response = getResponseLLAMA(content='', prompt_config=prompt_config_revise, prior_chat=prior_chat)

    print(revised_response)

    try:
        json_extracted = utils.parseMappingLLAMA(revised_response)
    except:
        print('Cannot extract out JSON from model drafted themes...')
        print(revised_response)
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
        print(f'Theme drafting error:', type(error).__name__, "-", error)
        print(revised_response)
        raise error

#Groups news posts into up to N buckets
def assignNewsPostsToThemes(posts: list, themes: list, topic_prompt_params: dict, prompt_config_init='default', prompt_config_revise='default') -> list[dict]:
    themes_str = json.dumps(themes)
    prompt_config_init = promptconfigs.COLLATION_PROMPTS['assign_theme_news_fn'](themes_str, topic_prompt_params) if prompt_config_init == 'default' else prompt_config_init
    prompt_config_revise = promptconfigs.COLLATION_PROMPTS['assign_theme_news_revise'] if prompt_config_revise == 'default' else prompt_config_revise
    content_long = ''
    content_short = ''

    #construct the string with all the posts
    for post in posts:
        content_long = content_long + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'
        content_short = content_short + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}"}}\n'

    #check if tokens exceeds max input, if so, just use titles no summary text
    content = content_long if utils.tokenCountLlama3(content_long) <= prompt_config_init['model_params']['truncate'] else content_short

    #first get initial mapping from model with base prompt
    initial_response, user_prompt = getResponseLLAMA(content, prompt_config_init, return_user_prompt=True)

    #then send model chat history and ask it to check for errors and revise
    prior_chat = [{
        'user': user_prompt,
        'assistant': initial_response
    }]
    revised_response = getResponseLLAMA(content='', prompt_config=prompt_config_revise, prior_chat=prior_chat)

    print(revised_response)

    try:
        json_extracted = utils.parseMappingLLAMA(revised_response)
    except:
        print('Cannot extract out JSON from model theme mapping...')
        print(revised_response)
        raise
    try:
        output = json.loads(json_extracted)
        return output
    except:
        print('Theme mapping from model not valid JSON, trying fix...')
    try:
        json_extracted = fixJSON(json_extracted)
        output = json.loads(json_extracted)
        return output
    except Exception as error:
        print(f'Theme mapping error:', type(error).__name__, "-", error)
        print(revised_response)
        raise error

#Groups similar/repeat headlines into stories - split into 2 steps, initial and revise
def groupNewsPostsToStories(posts: list, topic_prompt_params: dict, prompt_config_init='default', prompt_config_revise='default') -> list[dict]:
    prompt_config_init = promptconfigs.COLLATION_PROMPTS['group_story_news_fn'](topic_prompt_params) if prompt_config_init == 'default' else prompt_config_init
    prompt_config_revise = promptconfigs.COLLATION_PROMPTS['group_story_news_revise'] if prompt_config_revise == 'default' else prompt_config_revise
    content_long = ''
    content_short = ''
    #construct the string with all the posts
    for post in posts:
        content_long = content_long + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}", "summary": "{post['summary_ml']}"}}\n'
        content_short = content_short + f'{{"pid": {post['post_id']}, "title": "{post['retitle_ml']}"}}\n'

    #check if tokens exceeds max input, if so, just use titles no summary text
    content = content_long if utils.tokenCountLlama3(content_long) <= prompt_config_init['model_params']['truncate'] else content_short

    #first get initial mapping from model with base prompt
    initial_response, user_prompt = getResponseLLAMA(content, prompt_config_init, return_user_prompt=True)

    #then send model chat history and ask it to check for errors and revise
    prior_chat = [{
        'user': user_prompt,
        'assistant': initial_response
    }]
    revised_response = getResponseLLAMA(content='', prompt_config=prompt_config_revise, prior_chat=prior_chat)
    
    try:
        json_extracted = utils.parseMappingLLAMA(revised_response)
    except:
        print('Cannot extract JSON from model story mapping response')
        print(revised_response)
        raise
    try:
        output = json.loads(json_extracted)
        return output
    except:
        print('Story mapping from model not valid JSON, trying fix...')
    try:
        json_extracted = fixJSON(json_extracted)
        output = json.loads(json_extracted)
        return output
    except Exception as error:
        print(f'Story mapping error:', type(error).__name__, "-", error)
        print(revised_response)
        raise error

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
            filtered = max(enumerate(storyposts), key = lambda post: len((post[1]['post_text'] if post[1]['post_text'] is not None else '') + (post[1]['external_parsed_text'] if post[1]['external_parsed_text'] is not None else '')))
            del storyposts[filtered[0]]
            selected_posts.append(filtered[1])
            #out of remaining posts, get most likes post
            filtered = max(enumerate(storyposts), key = lambda post: (post[1]['likes_score'] if post[1]['likes_score'] is not None else 0))
            del storyposts[filtered[0]]
            selected_posts.append(filtered[1])

        #construct content string for model
        for i, post in enumerate(selected_posts):
            post_string = f'Post {i} headline: {post['retitle_ml']}\n\
                Post {i} text: {post['summary_ml']}\n\n'
            content = content + post_string
        #generate summary
        summary = getResponseLLAMA(content, prompt_config)
        posts_summarized = [post['post_id'] for post in selected_posts]
    return summary, posts_summarized

#write a short summary of the news within the theme
def generateThemeSummary(stories: list, topic_prompt_params: dict, prompt_config='default') -> str:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['theme_summary_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    #construct string combining all story summaries
    content = ''
    for idx, story in enumerate(stories):
        story_str = f'Story {idx} (i_score: {story['daily_i_score_ml']}) - {story['summary_ml']} \n\n'
        content = content + story_str
    return getResponseLLAMA(content, prompt_config)

#write a set of highlight bullets for the topic
def generateTopicSummary(stories: list, topic_prompt_params: dict, prompt_config='default') -> str:
    prompt_config = promptconfigs.SUMMARIZER_PROMPTS['topic_summary_news_fn'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    #construct string combining all story summaries
    content = ''
    for idx, story in enumerate(stories):
        story_str = f'Story {idx} (i_score: {story['daily_i_score_ml']}) - {story['summary_ml']} \n\n'
        content = content + story_str
    return getResponseLLAMA(content, prompt_config)

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
    prompt_config = promptconfigs.RANKING_PROMPTS['score_headlines_news'](topic_prompt_params) if prompt_config == 'default' else prompt_config
    content = ''
    for story in stories:
        content = content + f'{{"sid": {story['story_id']}, "summary": "{story['summary_ml']}"}}\n'
    
    raw_response = getResponseLLAMA(content, prompt_config)
    try:
        parsed_response = utils.parseMappingLLAMA(raw_response)
    except:
        print(raw_response)
        raise
    try:
        output = json.loads(parsed_response)
        return output
    except:
        print('Initial story scoring output not valid JSON, trying fix...')
    try:
        parsed_response = fixJSON(parsed_response)
        output = json.loads(parsed_response)
        return output
    except Exception as error:
        print(f'Story scoring error:', type(error).__name__, "-", error)
        print(raw_response)
        raise

#ERROR FIXING
##############################################################################################
def fixJSON(JSON_string: str, prompt_config='default') -> str:
    prompt_config = promptconfigs.ERROR_FIXING_PROMPTS['fix_JSON'] if prompt_config == 'default' else prompt_config
    return getResponseLLAMA(JSON_string, prompt_config)