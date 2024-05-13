#MODEL DEFAULTS
###################################################################

#Model
DEFAULT_MODEL = 'meta-llama/Meta-Llama-3-70B-Instruct'
DEFAULT_MODEL_PARAMS = {
    'temperature': 1.0,
    'truncate': 6144,
    'max_new_tokens': 2047,
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
def constructPromptLLAMA(user_prompt, system_prompt='') -> str:
    prompt = SYSTEM_PROMPT_PREPEND_LLAMA + system_prompt + ROLE_APPEND_LLAMA + USER_PROMPT_PREPEND_LLAMA + user_prompt + ROLE_APPEND_LLAMA + PROMPT_APPEND_LLAMA
    return prompt

#PROMPTS
###################################################################

#shared configs across multiple prompts
SUMMARY_LEN_NEWS = 150
SUMMARY_LEN_INSIGHTS = 250

#Prompts for classification
#REFACTOR this later to make categories reference separate variable
CLASSIFIER_PROMPTS = {
    'categorize':{
        'system_prompt': 'Your job is to categorize web content based on the source and a short text sample. \
            For example, the text can be a Reddit post headline or a tweet. Categories will be provided by the user. \
            Respond only with the label of the category and format your response as "#category#"',
        'user_prompt': 'Here are the possible categories:\n\
            - news: sharing or reporting current events\n\
            - insights: analysis, research, or educational article\n\
            - discussions: community conversations like asking questions or gathering opinions\n\
            - memes: jokes and other content meant to be funny\n\n\
            - other: does not fit in the above 4 categories\n\n\
            Choose the most likely category based on the following info. If you do not have enough info or are very uncertain, return "#other#".\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    },
}

#Functions for dynamic summarization prompts
def story_summary_news(topic_name):
    prompt = {
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize and edit. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to combine multiple posts about the same news story into a single summary. \
            I will provide the posts, which may include headlines, text from social media posts, and text from news articles.\n\n\
            \
            Your steps are as follows:\n\
            1. Read the content of all the posts.\n\
            2. Identify the most important facts and takeaways. Prioritize the info a {topic_name} enthusiast cares about most.\n\
            3. Summarize the key facts into 1 single summary paragraph. Include relevant quotes if they are important. Do not exceed {SUMMARY_LEN_NEWS} words.\n\
            4. Make the language engaging and entertaining so the reader will want to see more detailed content about the story.\n\n\
            \
            Combine the following posts:\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }
    return prompt

#Prompts for summarizing
SUMMARIZER_PROMPTS = {
    'news':{
        'system_prompt': 'You are an email newsletter writer. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to summarize news content for a reader that just wants the high-level important takeaways. \
            The content may include headlines, text from social media posts, and text from news articles.\n\n\
            \
            Your steps are as follows:\n\
            1. Ingest the provided information.\n\
            2. Understand the key facts of the news story and identify any important quotes.\n\
            3. Summarize the key facts into 1 paragraph and incorporate any important quotes. Do not exceed {SUMMARY_LEN_NEWS} words.\n\
            4. Make the language engaging and entertaining so the reader will want to see more detailed content about the story.\n\n\
            \
            Write a summary for the following content:\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }, 
    'insights':{
        'system_prompt': '',
        'user_prompt': f'Your task is to write a short summary of a new blog post or article for someone who does not have time to read the full thing.\n\n\
            \
            Follow this general structure for the summary:\n\
            1. Start by acknowledging the new blog post or article, in a few words.\n\
            2. Then, briefly explain the key insights from the article. This part should be the majority of the summary.\n\
            3. Then, in one highlighted sentence starting with "Why this matters:" explain the main implication and why the reader should care about it.\n\
            4. Finally, if necessary, invite the reader to read the full article for details.\n\n\
            \
            The writing style of the summary should be conversational and engaging. Use direct language and do not be verbose so it is easy to understand. \
            Write in third person only, do NOT write in first person.\n\n\
            \
            Write a summary for the following content, in {SUMMARY_LEN_INSIGHTS} words or less:\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    },
        'story_summary_news_fn': story_summary_news,
        'topic_summary_news':{
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize and edit. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to combine multiple news stories into a single highlights summary that a reader can quickly skim. \
            I will provide the content for each news story.\n\n\
            \
            Your steps are as follows:\n\
            1. Read the content of all the stories.\n\
            2. Prioritize the most important and impactful news. For example, exclusive or breaking news.\n\
            3. Summarize the most important news from all posts into 1 single summary paragraph. Do not exceed {SUMMARY_LEN_NEWS} words.\n\
            4. Make the language engaging and entertaining.\n\n\
            \
            Summarize the following stories:\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }
}

#Prompts for collation
COLLATION_PROMPTS = {
    'group_headlines_news':{
        'system_prompt': 'Your job is to group news posts that refer to the same story. The user will provide headlines in JSON format. \
            For example, {{"hid": 253, "h": "example headline"}}. Respond with JSON that maps each story id (sid) to a list of its headline ids (hid). \
            Each headline can only belong to 1 story. Do NOT map an hid to more than one sid. \
            Here is an example response format: [{{"sid": 0, "hid": [539,314,132]}}, {{"sid": 1, "hid": [792,646,927]}}, {{"sid": 2, "hid": [53,36,90]}}]. Do NOT respond with chat or other text.',
        'user_prompt': 'Evaluate the following headlines. Group the headlines that correspond to the same news story.\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }
}

#Functions for dynamic ranking prompts
def score_headlines_news(topic_name):
    prompt = {
        'system_prompt': f'Your job is to score news stories based on how much a Formula 1 enthusiast would care about it. The user will provide headlines in JSON format, for example {{"hid": 254, "h": "example headline"}}. \
            Score each headline with an importance score (i_score) in) and i_score. Here is an  the range 1-100. Do not assign the same score to multiple headlines. \
            Format your response as a JSON list with headline id (hid) and i_score. Here is an example response: [{{"hid": 157, "i_score": 84}}, {{"hid": 942, "i_score": 52}}, {{"hid": 418, "i_score": 16}}]. \
            ONLY respond with JSON, do NOT respond with text.',
        'user_prompt': f'Your task is to score news stories based on importance to a {topic_name} enthusiast. Higher i_score means more important. Evaluate the following stories: \n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }
    return prompt

#Prompts for selection and ranking
RANKING_PROMPTS = {
    'score_headlines_news': score_headlines_news
}

#Prompts for writing headlines
HEADLINE_PROMPTS = {
    'news_headline':{
        'system_prompt': 'You are an email newsletter writer. The user will provide news content and ask you to write a headline. Respond ONLY with the headline, do NOT respond with chat.',
        'user_prompt': 'Your task is to write a short, descriptive headline for a piece of trending news to attract the attention of readers. \
            Do not include quotes in the headline. \
            Write an engaging headline for the following news, in 15 words or less:\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }
}

#Prompts for ensuring model outputs exact required format
ERROR_FIXING_PROMPTS = {
    'fix_JSON':{
        'system_prompt': 'Your job is to check JSON lists for syntax errors and fix them. The user will provide you with a JSON list. Respond with ONLY the updated JSON list. Do NOT respond with text.',
        'user_prompt': 'Check this JSON list for syntax errors and fix them. Do NOT modify the data.',
        'model_params': DEFAULT_MODEL_PARAMS
    }
}

###OLD ARCHIVED###
#Prompts for insight headline
HEADLINE_INSIGHTS_SYSTEM_PROMPT = '''Your task is to write a short headline telling readers about a new blog post, article, or opinion piece'''
HEADLINE_INSIGHTS_PREPEND = '''Confidently write an engaging headline based on the following article summary, in 15 words or less.\n\n'''
HEADLINE_INSIGHTS_MODEL_PARAMS = DEFAULT_MODEL_PARAMS

#old test editor prompt
old_editor_news_prompt = {
    'edit_news':{
        'system_prompt': 'You are an editor of an email newsletter. Your job is to edit the content to improve quality and readability. \
            Make sure to provide a response after each step of editing, then provide the final edited summary with the header "[FINAL SUMMARY]"',
        'user_prompt': f'Your task is to edit summaries of news stories, social media posts, and articles to improve quality and readability.\n\n\
            \
            Here are the instructions to edit:\n\
            1. Make sure the summary mentions the new article in the first sentence.\n\
            2. Identify any sentences that require expert knowledge to understand (e.g. acronyms, specialized terms, etc.) and reword it in a way that is easy to understand for a general audience.\n\
            3. Identify any sentences that are overly verbose, hard to read, or have repetitive information, and reword these.\n\
            4. Make sure the length of the summary is less than {SUMMARY_LEN_NEWS} words.\n\
            5. Make sure the summary is written in third person NOT first person.\n\n\
            \
            Edit the following summary according to your instructions:\n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }
}