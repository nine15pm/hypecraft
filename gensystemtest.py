import ollama as o
from getheadlines import getRedditPosts, getSubstackPosts
import time
import json
import trafilatura
import mimetypes

#CONFIGS
##############################################################################################
#General
PATH_SUMMARIES_REDDIT = 'summaries_reddit.json'
PATH_SUMMARIES_SUBSTACK = 'summaries_substack.json'

#SUMMARIZER_TITLE_PREPEND = '''Use your best effort to confidently write a hyped clickbait headline for the following content, in 15 words or less:\n\n'''

#Summarizer
SUMMARIZER_MODEL = 'llama3'
SUMMARIZER_SYSTEM_PROMPT = '''Your task is to write a summary of a trending piece of content from a blog, Twitter, Reddit, or other sources. 
Write in a style that is conversational, direct, and engaging, like chatting with a good friend. 
Use jokes and sarcasm in the summary to be more entertaining. 
The summary should be highly appealing to read for a young audience. '''
SUMMARIZER_PREPEND = '''Use your best effort to provide a summary of the following content, in 200 words or less. Do NOT write in first person.\n\n'''
SUMMARIZER_MODEL_PARAMS = {
    'mirostat': 2,
    'temperature': 0.6,
}

#Editor
EDITOR_MODEL = SUMMARIZER_MODEL
EDITOR_SYSTEM_PROMPT = '''You are an editor of newsletter content. 
Your task is to edit the summaries of stories to ensure consistent formatting, ensure consistent tone, and improve clarity.  
For example, to ensure good formatting you should remove any unnecessary quotation marks, brackets, or markup that should not be shown to the reader. 
For example, to ensure consistent tone you should reword anything the author wrote in first person (e.g. "we" or "our") into third person. 
For example, to improve clarity, you may choose to condense or edit sentences that have redundant information. '''
EDITOR_PREPEND = '''Make edits to the following summary and provide the ONLY text of the improved version. Do NOT respond with chat or comments.\n\n'''
EDITOR_MODEL_PARAMS = {
    'mirostat': 2,
    'temperature': 0.6
}

#FUNCTIONS
##############################################################################################
#Use model to summarize raw content text
def summarizeContent(content_text):
    output = o.generate(
        model = SUMMARIZER_MODEL,
        prompt = SUMMARIZER_PREPEND + content_text,
        system = SUMMARIZER_SYSTEM_PROMPT,
        options = SUMMARIZER_MODEL_PARAMS,
        stream = False
    )
    print(output['prompt_eval_count'])
    return output['response']

#Use model to edit output summaries to ensure consistent formatting, tone, quality
def editSummary(summary_text):
    output = o.generate(
        model = EDITOR_MODEL,
        prompt = EDITOR_PREPEND + summary_text,
        system = EDITOR_SYSTEM_PROMPT,
        options = EDITOR_MODEL_PARAMS,
        stream = False
    )
    return output['response']


def editSummary(summary_text):
    output = o.generate(
        model = EDITOR_MODEL,
        prompt = EDITOR_PREPEND + summary_text,
        system = EDITOR_SYSTEM_PROMPT,
        options = EDITOR_MODEL_PARAMS,
        stream = False
    )
    return output['response']

#Save to local json file
def saveJSON(data, path):
    with open(path, 'w') as outfile:
        json.dump(data, outfile)

#Read from local json file
def loadJSON(path):
    with open(path, 'r') as infile:
        return json.load(infile)

#GENERATION TEST
##############################################################################################
subreddit = 'formula1'
substack = 'semianalysis'
last30days = time.time() - 2.6e6 #get current time minus 30 days

#Get posts from sources
subreddit_posts = getRedditPosts(subreddit, max_posts=2, newer_than_datetime=last30days)
substack_posts = getSubstackPosts(substack, newer_than_datetime=last30days)

#Generate and save summaries of individual posts
reddit_summaries = []
substack_summaries = []

for post in subreddit_posts:
    if post['linked_content'] is not None:
        post_title = post['headline']
        post_text = post['post_text'] if post['post_text'] is not None else ""

        #this logic is super hacky and garbage, REFACTOR later
        if post['linked_content'] is not None:
            content_type = mimetypes.guess_type(post['linked_content'])[0]
            if 'image' in str(content_type) or content_type == None:
                linked_text = ""
            else:
                source_data = trafilatura.fetch_url(post['linked_content'])
                linked_text = trafilatura.extract(source_data)
        else:
            linked_text = ""
        
        content = post_title + "/n" + post_text + "/n/n" + linked_text
        original = summarizeContent(content)
        edited = editSummary(original)
        print('EDITED----------------')
        print(edited)
        reddit_summaries.append(edited)

for post in substack_posts:
    post_title = post['headline']
    post_description = post['description'] if post['description'] is not None else ""
    post_content = post['post_content']
    content = post_title + "/n" + post_description + "/n/n" + post_content
    original = summarizeContent(content)
    print('ORIGINAL----------------')
    print(original)
    edited = editSummary(original)
    print('EDITED----------------')
    print(edited)
    substack_summaries.append(edited)

#save summaries to local file
saveJSON(reddit_summaries, PATH_SUMMARIES_REDDIT)
saveJSON(substack_summaries, PATH_SUMMARIES_SUBSTACK)

#Assemble newsletter


