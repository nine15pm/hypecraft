import configs

#MODEL DEFAULTS
###################################################################

#Model
DEFAULT_MODEL = configs.DEFAULT_MODEL
DEFAULT_MODEL_PARAMS = {
    'temperature': 0.6,
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
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
        'user_prompt': f'Your task is to combine multiple posts about the same news story into a single summary. \
            The post content may include headlines, text from social media posts, and text from news articles.\n\n\
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

def topic_summary_news(topic_name):
    prompt = {
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize. Respond ONLY with the summary bullets, do NOT respond with chat.',
        'user_prompt': f'Your task is to summarize top {topic_name} news stories into a bulleted list of highlights that a reader can quickly skim. \n\n\
            \
            Your steps are as follows:\n\
            1. Read the content of all the stories.\n\
            2. Select 3-5 of the most important stories. Prioritize exclusive or breaking news, the info a {topic_name} enthusiast cares about most.\n\
            3. Write a list of bulleted highlights, 1 for each selected story. Order the highest i_score stories first. Make the language engaging and entertaining.\n\n\
            \
            Summarize the following stories:\n\n',
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
        'system_prompt': 'You are an email newsletter writer. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
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
        'topic_summary_news': topic_summary_news,
        'topic_summary_news_old':{
        'system_prompt': 'You are an email newsletter editor. The user will provide content for you to summarize. Respond ONLY with the summary, do NOT respond with chat.',
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

#Functions for collation prompts
def group_news(topic_name):
    prompt = {
        'system_prompt': 'Your job is to group news posts that refer to the same story. The user will provide posts in JSON format. Do the task step by step.',
        'user_prompt': f'Your task is to map {topic_name} news posts into stories according to the following steps:\n\
            1. Read through the content of each posts \n\
            2. Identify and list out each distinct news story and its related post ids. Make sure to list EVERY distinct story separately. Each post can only be assigned to 1 story. \n\
            3. Format the list of stories into a JSON list. Here is an example: [{{"sid": 0, "pid": [31,63]}}, {{"sid": 1, "pid": [53,46,24]}}, {{"sid": 2, "pid": [97]}}]. \n\n\
            Go step by step and group the posts below: \n\n',
        'model_params': DEFAULT_MODEL_PARAMS
    }
    return prompt

def OLD_check_group_news(topic_name):
    prompt = {
        'system_prompt': 'Your job is to group news posts that refer to the same story. The user will provide posts in JSON format. \
            Respond with JSON that maps a list of posts (pid) to a story (sid). \
            Here is an example response format: [{{"sid": 0, "pid": [53,13]}}, {{"sid": 1, "pid": [92,46,27]}}, {{"sid": 2, "pid": [153]}}]. Do NOT respond with chat or text.',
        'user_prompt': f'There are some mistakes, some posts grouped together refer to different news stories. Review the post summaries in each group as a {topic_name} enthusiast and fix the grouping errors. Respond with ONLY the updated JSON list.',
        'model_params': DEFAULT_MODEL_PARAMS
    }
    return prompt

#Prompts for collation
COLLATION_PROMPTS = {
    'group_news':group_news
}

#Functions for dynamic ranking prompts
def score_headlines_news(topic_name):
    prompt = {
        'system_prompt': 'Your job is to score news stories to determine how they should be prioritized in a newsletter. The user will provide stories in JSON format. Do the task step by step.',
        'user_prompt': f'Your task is to score {topic_name} news stories according to the following steps: \n\
            1. Read each story \n\
            2. Evaluate how interesting the story is to a {topic_name} enthusiast. Prioritize exclusive, breaking news with big potential impact. \n\
            3. List out a brief summary assessment for each story. \n\
            3. Assign a score from 1-100 to each story based on your assessment. Higher score means more important. Do not assign the same score to multiple stories. \n\
            4. Format the scores as a JSON list. Here is an example: [{{"sid": 157, "i_score": 71}}, {{"sid": 942, "i_score": 42}}, {{"sid": 418, "i_score": 16}}]. \n\
            Go step by step and evaluate the stories below: \n\n',
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