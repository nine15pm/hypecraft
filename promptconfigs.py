#MODEL PARAMS
###################################################################

#Model params llama
TASK_MODEL_PARAMS_OPENAI = {
    'temperature': 0.7,
    'max_new_tokens': 3000,
    'top_p': 1.0
}

TASK_MODEL_PARAMS_LLAMA = {
    'temperature': 0.6,
    'truncate': 6144,
    'max_new_tokens': 2047,
    'top_p': 0.9,
    'stop': ['<|eot_id|>'],
    'stop_sequences': ['<|eot_id|>'],
    'return_full_text': False
}

BRAINSTORM_MODEL_PARAMS_LLAMA = {
    'temperature': 0.75,
    'truncate': 6144,
    'max_new_tokens': 2047,
    'top_p': 0.9,
    'stop': ['<|eot_id|>'],
    'stop_sequences': ['<|eot_id|>'],
    'return_full_text': False
}

WRITING_MODEL_PARAMS = {
    'temperature': 0.9,
    'truncate': 6144,
    'max_new_tokens': 2047,
    'top_p': 0.9,
    'stop': ['<|eot_id|>'],
    'stop_sequences': ['<|eot_id|>'],
    'return_full_text': False
}

#LLAMA prompt structure
SYSTEM_PROMPT_PREPEND_LLAMA = '<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n'
USER_PROMPT_PREPEND_LLAMA = '<|start_header_id|>user<|end_header_id|>\n\n'
ROLE_APPEND_LLAMA = '<|eot_id|>'
PROMPT_APPEND_LLAMA = '<|start_header_id|>assistant<|end_header_id|>\n\n'

#HELPER FUNCTIONS
###################################################################
def constructPromptLLAMA(user_prompt, prior_chat: list[dict] = None, system_prompt='') -> str:
    if prior_chat is not None:
        prompt = SYSTEM_PROMPT_PREPEND_LLAMA + system_prompt + ROLE_APPEND_LLAMA
        #add in each set of prior chat and response
        for chat in prior_chat:
            prompt = prompt + USER_PROMPT_PREPEND_LLAMA + chat['user'] + ROLE_APPEND_LLAMA + PROMPT_APPEND_LLAMA + chat['assistant'] + ROLE_APPEND_LLAMA
        #add in the new user prompt
        prompt = prompt + USER_PROMPT_PREPEND_LLAMA + user_prompt + ROLE_APPEND_LLAMA + PROMPT_APPEND_LLAMA
    else:
        prompt = SYSTEM_PROMPT_PREPEND_LLAMA + system_prompt + ROLE_APPEND_LLAMA + USER_PROMPT_PREPEND_LLAMA + user_prompt + ROLE_APPEND_LLAMA + PROMPT_APPEND_LLAMA
    #print(prompt)
    return prompt

def constructPromptOPENAI(user_prompt, prior_chat: list[dict] = None, system_prompt='') -> list[dict]:
    messages = []
    #add system prompt
    messages.append({'role': 'system', 'content': system_prompt})
    if prior_chat is not None:
        #add in each set of prior chat and response
        for chat in prior_chat:
            messages.append({'role': 'user', 'content': chat['user']})
            messages.append({'role': 'assistant', 'content': chat['assistant']})
        #add in the new user prompt
        messages.append({'role': 'user', 'content': user_prompt})
    else:
        #just append new user prompt with no history
        messages.append({'role': 'user', 'content': user_prompt})
    #print(messages)
    return messages

def constructSFREmbedQuery(task_description:str, query:str):
    return f'Instruct: {task_description}\nQuery: {query}'

#PROMPTS
###################################################################

#shared configs across multiple prompts
SUMMARY_LEN_NEWS = 150
SUMMARY_LEN_INSIGHTS = 250

#RAG search prompts
RAG_SEARCH_TASKS = {
    'similar_news': 'Given a piece of news, retrieve relevant passages about the same news story - e.g. prior developments, related context'
}

#Prompts for classification
#REFACTOR this later to make categories reference separate variable
CLASSIFIER_PROMPTS = {
    'categorize':{
        'system_prompt': 'Your job is to categorize web content based on the source and extracted text. For example, a Reddit post, a blog post, or a tweet. Categories will be provided by the user. Respond only with the label of the category and format your response as "#category#"',
        'user_prompt': 'Here are the possible categories:\n\
            - news: sharing or reporting current events\n\
            - insights: analysis, research, or educational article\n\
            - opinion: editorial pieces or personal opinions\n\
            - discussions: community conversations, debates, or Q&A\n\
            - memes: jokes and other content meant to be funny\n\
            - junk: advertisments, company promotions, website error pages, and other junk content\n\
            - other: does not fit any category above\n\n\
        Choose the most likely category based on the following info. If you do not have enough info or are very uncertain, return "#other#".\n\n',
        'model_params': TASK_MODEL_PARAMS_LLAMA
    },
}

#Functions for dynamic summarization prompts
def post_summary_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter writer. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to summarize {topic_prompt_params['topic_name']}a news content. The content may include headlines, text from social media posts, and text from news articles.\n\n\
        Your instructions:\n\
            1. Ingest the provided content.\n\
            2. Understand the key facts of the news story and identify any important quotes.\n\
            3. Summarize all the key facts into 1 paragraph and incorporate any important quotes. Do not exceed {SUMMARY_LEN_NEWS} words.\n\
        Write a summary for the following content:\n\n',
        'model_params': TASK_MODEL_PARAMS_LLAMA
    }
    return prompt

def story_summary_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to combine multiple posts about the same news story into a single summary. \
        The post content may include headlines, text from social media posts, and text from news articles.\n\n\
        Your steps are as follows:\n\
            1. Read the content of all the posts.\n\
            2. Identify the most important facts and takeaways. Prioritize the info a {topic_prompt_params['topic_name']} enthusiast cares about most.\n\
            3. Summarize the key facts into 1 single summary paragraph. Include relevant quotes if they are important. Do not exceed {SUMMARY_LEN_NEWS} words.\n\
            4. Make the language concise, conversational, and engaging to read. Avoid using unnecessary complex words. \n\n\
        Combine the following posts:\n\n',
        'model_params': WRITING_MODEL_PARAMS
    }
    return prompt

def theme_summary_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to summarize top {topic_prompt_params['topic_name']} news stories into a 1 line highlight that a reader can quickly skim. \n\n\
        Your steps are as follows:\n\
            1. Identify the news that a {topic_prompt_params['topic_name']} enthusiast would care most about. \n\
            2. Write a concise 1 line highlight previewing this news. Mention the highest i_score stories first and prioritize exclusive or breaking news. Make the language engaging and entertaining.\n\n\
        Summarize the following stories:\n\n',
        'model_params': WRITING_MODEL_PARAMS
    }
    return prompt

def topic_summary_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize. Respond ONLY with the summary bullets, do NOT respond with chat.',
        'user_prompt': f'Your task is to summarize top {topic_prompt_params['topic_name']} news stories into a bulleted list of highlights that a reader can quickly skim. \n\n\
        Your steps are as follows:\n\
            1. Read the content of all the stories. Prioritize exclusive or breaking news, the info a {topic_prompt_params['topic_name']} enthusiast cares about most.\n\
            3. Write a list of bulleted highlights, 1 for each story. Order the highest i_score stories first. Make the language concise, conversational, and easy to understand.\n\n\
        Summarize the following stories:\n\n',
        'model_params': WRITING_MODEL_PARAMS
    }
    return prompt

#Prompts for summarizing
SUMMARIZER_PROMPTS = {
    'post_summary_news_fn': post_summary_news, 
    'insights':{
        'system_prompt': 'You are an email newsletter writer. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to write a short summary of a new blog post or article for someone who does not have time to read the full thing.\n\n\
        Follow this general structure for the summary:\n\
            1. Start by acknowledging the new blog post or article, in a few words.\n\
            2. Then, briefly explain the key insights from the article. This part should be the majority of the summary.\n\
            3. Then, in one highlighted sentence starting with "Why this matters:" explain the main implication and why the reader should care about it.\n\
            4. Finally, if necessary, invite the reader to read the full article for details.\n\n\
        The writing style of the summary should be conversational and engaging. Use direct language and do not be verbose so it is easy to understand. Write in third person only, do NOT write in first person.\n\n\
        Write a summary for the following content, in {SUMMARY_LEN_INSIGHTS} words or less:\n\n',
        'model_params': WRITING_MODEL_PARAMS
    },
    'story_summary_news_fn': story_summary_news,
    'theme_summary_news_fn': theme_summary_news,
    'topic_summary_news_fn': topic_summary_news
}

#Functions for collation prompts
def filter_outdated_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter editor. The user will provide you news posts in JSON format and instructions. Your task is to identify outdated news posts given the context of other news posts. Go step by step and write out each step.',
        'user_prompt': f'Follow these steps to identify outdated posts:\n\
            1.  Go through each post and identify whether it is outdated. For example, if Post A is about rumors of an event, and Post B is a report after the event has happened, then Post A is outdated. Duplicate or redundant posts are OK as long as they are not outdated. \n\
            3. Return a formatted JSON list of all the posts and whether each is outdated (true or false). For example: [{{"pid": 261, "outdated": true}}, {{"pid": 94, "outdated": false}}, {{"pid": 433, "outdated": true}}] \n\
        Go step by step and identify outdated posts. \n\n',
        'model_params': TASK_MODEL_PARAMS_OPENAI
    }
    return prompt

def group_story_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter editor. The user will provide you news posts in JSON format and instructions. Your task is identify posts about the same news story. Go step by step and write out each step.',
        'user_prompt': f'Follow these steps to map news posts:\n\
            1. Find and list every case where multiple posts are discussing the same broad news story. Cite the post ids and write out the rationale. \n\
            3. Provide a formatted JSON list of all the posts grouped into stories. Every post must be mapped to at least 1 story. Here is an example: [{{"sid": 1, "pid": [31,63]}}, {{"sid": 2, "pid": [53,46,24]}}, {{"sid": 3, "pid": [97]}}]. \n\
        Go step by step and map the posts. \n\n',
        'model_params': TASK_MODEL_PARAMS_OPENAI
    }
    return prompt

def brainstorm_theme_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter editor. The user will provide posts and instructions. Your job is to come up with ideas for newsletter sections. Make sure to format the ideas in a JSON list',
        'user_prompt': f'Your task is to come up with ideas for sections for a {topic_prompt_params['topic_name']} newsletter:\n\
            1. Draft a list of 10 ideas of well-defined section names. Each section idea should CLOSELY and DIRECTLY fit multiple news posts (the more the better). Section names should be short and catchy, e.g. {topic_prompt_params['theme_examples']}. One of the sections can be "Other" if there are posts that do not fit well. \n\
            2. Format the list of sections as a JSON list. For example: [{{"id": 1, "name": "Section A"}}, {{"id": 2, "name": "Section B"}}, {{"id": 3, "name": "Section C"}}] \n\n\
        Go step by step and come up with section ideas for the posts below: \n\n',
        'model_params': BRAINSTORM_MODEL_PARAMS_LLAMA
    }
    return prompt

def select_theme_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter editor. The user will provide instructions, section options, and news posts. Go step by step and write out each step.',
        'user_prompt': f'Your task is to evaluate different options for newsletter sections and come up with a final set of sections that best fits the provided news posts. Follow these steps: \n\
            1. Write a 1-line assessment of the fit of each option with the news posts. Criteria to consider: \n\
                - Closely and directly fits multiple news posts \n\
                - Focuses on 1 topic or theme, specific to {topic_prompt_params['topic_name']} \n\
                - Short, engaging, not repetitive name \n\
                - Not vague or overly broad, has minimum overlap with other sections \n\
            2. Select a set of 3-5 sections that best fits the news posts. Include 1 "Other" section for posts that do not fit. \n\
            3. Assign each post (id, title) to a section. \n\
            4. Review each section and assigned posts - identify any case of the following errors: \n\
                - Post is not perfectly related to section \n\
                - Section has overlap with another section \n\
                - Posts about same story assigned to different sections \n\
                - Section is empty \n\
            5. Fix the issues, add or remove sections if needed. Provide a final list of sections, do NOT exceed 5 sections. \n\
            6. Format the sections as a JSON list. For example: [{{"id": 1, "name": "Section A", "scope": "Covers x, y, z types of stories"}}, {{"id": 2, "name": "Section B", "scope": "Covers x, y, z types of stories"}}, {{"id": 3, "name": "Section C", "scope": "Covers x, y, z types of stories"}}] \n\n',
        'model_params': TASK_MODEL_PARAMS_OPENAI
    }
    return prompt

def assign_theme_news(themes:str, topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter editor. The user will provide you news posts in JSON format and instructions. Your task is to assign each news post to the appropriate section of the newsletter. Go step by step and write out each step.',
        'user_prompt': f'Your task is to assign each {topic_prompt_params['topic_name']} news post to the appropriate section of a newsletter according to the following steps:\n\
            1. For each post, evaluate which of the following sections it best fits into and write out your rationale. If a post does not fit any section and there is an "Other" section, you can assign it to "Other". \n\
                {themes} \
            2. Check your work for mistakes: \n\
                - Make sure all posts about the same story are assigned to the same section. \n\
                - Make sure the news story of each posts actually fits the assigned section. \n\
                - Make sure similar types of news stories are consistently assigned, e.g. all posts about {topic_prompt_params['assign_theme_examples']} should be in the same section. \n\
            3. Make corrections if needed. \n\
            4. Provide a formatted JSON list of posts grouped by section. Make sure every post is assigned a section. Do NOT assign a post to more than 1 section. Here is an example: [{{"pid": 63, "section": 1}}, {{"pid": 19, "section": 3]}}, {{"pid": 812, "section": 2}}] \n\n',
        'model_params': TASK_MODEL_PARAMS_OPENAI
    }
    return prompt

#Prompts for collation
COLLATION_PROMPTS = {
    'filter_outdated_news_fn': filter_outdated_news,
    'group_story_news_fn': group_story_news,
    'brainstorm_theme_news_fn': brainstorm_theme_news,
    'select_theme_news_fn': select_theme_news,
    'assign_theme_news_fn': assign_theme_news
}

#Functions for dynamic ranking prompts
def score_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter editor. The user will provide you news stories in JSON format and instructions. Your task is to score the importance of news stories. Go step by step and write out each step.',
        'user_prompt': f'Follow these steps: \n\
            1. Evaluate how important the news is to a {topic_prompt_params['topic_name']} enthusiast. Prioritize exclusive, surprising, or breaking news with big potential impact. \n\
            2. List out a brief summary assessment for each story. \n\
            3. Assign a score from 1-100 to each story based on your assessment. Higher score means more important. Do not assign the same score to multiple stories. \n\
            4. Format the scores as a JSON list. Here is an example: [{{"sid": 157, "i_score": 71}}, {{"sid": 942, "i_score": 42}}, {{"sid": 418, "i_score": 16}}]. \n\
        Go step by step and evaluate the stories.\n\n',
        'model_params': TASK_MODEL_PARAMS_OPENAI
    }
    return prompt

#Prompts for selection and ranking
RANKING_PROMPTS = {
    'score_news_fn': score_news
}

#Prompts for writing headlines
HEADLINE_PROMPTS = {
    'news_headline':{
        'system_prompt': 'You are an email newsletter writer. The user will provide news content and ask you to write a headline. Respond ONLY with the headline, do NOT respond with chat.',
        'user_prompt': 'Your task is to write a short, descriptive headline for a piece of trending news to attract the attention of readers. Do not include quotes in the headline. Write an engaging headline for the following news, in 15 words or less:\n\n',
        'model_params': WRITING_MODEL_PARAMS
    },
    'news_post_retitle':{
        'system_prompt': 'The user will provide news content for you to describe. Respond ONLY with the 1-line summary, do NOT respond with chat.',
        'user_prompt': 'Your task is to write a 1-line summary of the main news story discussed in the post below. Do NOT exceed 15 words. \n\n',
        'model_params': TASK_MODEL_PARAMS_LLAMA
    }
}

#Prompts for ensuring model outputs exact required format
ERROR_FIXING_PROMPTS = {
    'fix_JSON':{
        'system_prompt': 'Your job is to check JSON lists for syntax errors and fix them. The user will provide you with a JSON list. Respond with ONLY the updated JSON list. Do NOT respond with text.',
        'user_prompt': 'Check this JSON list for syntax errors and fix them. Do NOT modify the data.',
        'model_params': TASK_MODEL_PARAMS_LLAMA
    }
}



####ARCHIVED PROMPTS####
###############################################################################################################################################
'''

def draft_theme_news_revise(topic_prompt_params:dict):
    prompt = {
        'system_prompt': f'You are a {topic_prompt_params['topic_name']} newsletter editor. The user will provide you news posts in JSON format and instructions. Your task is to come up with a set of newsletter sections that best fits the provided news posts. Go step by step and write out each step.',
        'user_prompt': f'1. Review each section (except for "Other") and write out a detailed evaluation:\n\
            - Does it overlap with another section? \n\
            - Are posts about the same story split into different sections? \n\
            - Is it too vague and not specific to {topic_prompt_params['topic_name']}? \n\
            - Is the naming too awkward or boring? \n\
        2. Make improvements, add or remove sections if needed, and provide an updated JSON list of sections. \n\n',
        'model_params': TASK_MODEL_PARAMS_OPENAI
    }
    return prompt

def group_story_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': 'Your job is to group news posts that refer to the same story. The user will provide posts in JSON format. Make sure to do the task step by step and write out every step.',
        'user_prompt': f'Your task is to map {topic_prompt_params['topic_name']} news posts according to the following steps:\n\
            1. Read through the posts \n\
            2. Find and list every case where there are multiple posts discussing the same news story. Cite the posts and write out the rationale. \n\
            3. Provide a formatted JSON list of these cases. Here is an example: [{{"sid": 0, "pid": [31,63]}}, {{"sid": 1, "pid": [53,46,24]}}, {{"sid": 2, "pid": [97]}}]. \n\
            4. If there are no cases, return an empty JSON list [{{}}] \n\n\
        Go step by step and group the posts below: \n\n',
        'model_params': TASK_MODEL_PARAMS
    }
    return prompt

def draft_theme_news(topic_prompt_params:dict):
    prompt = {
        'system_prompt': 'Your job is to group related news posts. The user will provide posts in JSON format. Make sure to do the task step by step and write out every step.',
        'user_prompt': f'Your task is to group {topic_prompt_params['topic_name']} news posts into newsletter sections according to the following steps:\n\
            1. Read through the posts \n\
            2. Draft a list of up to 5 WELL-DEFINED DISTINCT sections that best covers all of the news stories discussed. Make sure section names are short and catchy, e.g. {topic_prompt_params['theme_examples']}. 1 section can be "Other" if there are posts that do not fit. Do NOT have more than 5 sections. \n\
            3. Review each section and evaluate: Does the section make sense for a newsletter? Is it too vague or broad? Does it overlap with another section? Make improvements and provide an updated list of sections. \n\
            4. Format the list of sections as a JSON list. For example: [{{"id": 1, "name": "Section A"}}, {{"id": 2, "name": "Section B"}}, {{"id": 3, "name": "Section C"}}] \n\n\
        Go step by step and come up with sections for the posts below: \n\n',
        'model_params': WRITING_MODEL_PARAMS
    }
    return prompt

def draft_theme_news_revise(topic_prompt_params:dict):
    prompt = {
        'system_prompt': 'Your job is to group related news posts. The user will provide posts in JSON format. Make sure to do the task step by step and write out every step.',
        'user_prompt': f'1. Review each section (except for "Other") and write out a detailed evaluation:\n\
            - Does the section make sense for a {topic_prompt_params['topic_name']} newsletter? \n\
            - Does it overlap with another section? Is it mutually exclusive, collectively exhaustive? \n\
            - Is it too vague or broad? \n\
            - Is the naming short, catchy, and not awkward? \n\
            - Is it too niche or infrequent a topic? \n\
        2. Make improvements if needed and provide an updated JSON list of sections. \n\n',
        'model_params': TASK_MODEL_PARAMS
    }
    return prompt

def assign_theme_news(themes:str, topic_prompt_params:dict):
    prompt = {
        'system_prompt': 'Your job is to group related news posts. The user will provide posts in JSON format. Make sure to do the task step by step and write out every step.',
        'user_prompt': f'Your task is to assign each {topic_prompt_params['topic_name']} news post to the appropriate section of a newsletter according to the following steps:\n\
            1. Read through the posts \n\
            2. For each post, evaluate which of the following sections it might best fit into and explain your rationale. \n\
                {themes} \
            3. Based on your evaluations, list the best section for each post. \n\
            4. Provide a formatted JSON list of posts with sections. Make sure every post is assigned a section. Do NOT assign a post more than 1 section. For example: [{{"pid": 63, "section": 1}}, {{"pid": 19, "section": 3]}}, {{"pid": 812, "section": 2}}] \n\n\
        Go step by step and assign the posts below: \n\n',
        'model_params': TASK_MODEL_PARAMS
    }
    return prompt

#Prompts for collation
COLLATION_PROMPTS = {
    'group_story_news_fn': group_story_news,
    'draft_theme_news_fn': draft_theme_news,
    'draft_theme_news_revise_fn': draft_theme_news_revise,
    'assign_theme_news_fn': assign_theme_news,
    'group_story_news_revise': {
        'system_prompt': 'Your job is to group news posts that refer to the same story. The user will provide posts in JSON format. Make sure to do the task step by step and write out every step.',
        'user_prompt': f'1. Review the posts in each grouping and check whether there are posts that do not fit. Write out your assessment. \n\
            2. Check whether there are posts discussing the same broad story assigned to different groupings. MAKE SURE posts about the same story are always in the same grouping. Write out your assessment. \n\
            3. If needed, update any groupings. \n\
            4. Provide an updated JSON list. If there are no groupings, return an empty JSON list [{{}}]',
        'model_params': TASK_MODEL_PARAMS
    },
    'assign_theme_news_revise': {
        'system_prompt': 'Your job is to group related news posts. The user will provide posts in JSON format. Make sure to do the task step by step and write out every step.',
        'user_prompt': f'1. Review each post and its section, evaluate whether the section is a good fit (use common sense), write out your rationale. \n\
            2. MAKE SURE posts about the same broad story are ALWAYS assigned to the same section. \n\
            2. If needed, update post assignments. \n\
            3. Provide an updated JSON list.',
        'model_params': TASK_MODEL_PARAMS
    }
}
'''