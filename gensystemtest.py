import ollama as o
from getheadlines import getRedditPosts, getSubstackPosts
import time
import trafilatura
import requests
import mimetypes

#Configs
SUMMARIZER_MODEL = 'phi3'
EMAIL_GEN_MODEL = 'phi3'

SUMMARIZER_SYSTEM_PROMPT = '''You are the 21-year old author of a popular daily email newsletter.
The newsletter covers many topics, like AI, sports, culture, and fitness.
Your job is to take trending content from blogs, Twitter, Reddit, and other sources and summarize it.
Your writing style is conversational, direct, and engaging like talking to an interesting friend. You often use jokes and sarcasm in your writing to be more entertaining.
Your summaries should be highly appealing to read for a young audience.'''

HEADLINE_USER_PROMPT_PREPEND = '''Use your best effort to confidently write a hyped clickbait headline for the following content in 15 words or less:\n\n'''
SUMMARY_USER_PROMPT_PREPEND = '''Now, use your best effort to confidently write an engaging summary in 200 words or less.'''

#Function to call model and return json of summary {headline:, summary:}
def summarizeContent(content_text):
    title = o.chat(
        model = SUMMARIZER_MODEL,
        messages = [
            {'role': 'system', 'content': SUMMARIZER_SYSTEM_PROMPT},
            {'role': 'user', 'content': HEADLINE_USER_PROMPT_PREPEND + content_text}
            ],
        format='json',
        stream = False
        )
    body = o.chat(
        model = SUMMARIZER_MODEL,
        messages = [
            {'role': 'system', 'content': SUMMARIZER_SYSTEM_PROMPT},
            {'role': 'user', 'content': HEADLINE_USER_PROMPT_PREPEND + content_text},
            {'role': 'assistant', 'content': title['message']['content'].strip()},
            {'role': 'user', 'content': SUMMARY_USER_PROMPT_PREPEND}
            ],
        format='json',
        stream = False
        )
    summary = {
        'headline': title['message']['content'].strip(),
        'summary': body['message']['content'].strip()
    }
    return summary

#Generation test using a a test substack and subreddit
subreddit = 'formula1'
substack = 'semianalysis'
last7days = time.time() - 604800 #get current time minus 7 days

subreddit_posts = getRedditPosts(subreddit, max_posts=2, newer_than_datetime=last7days)
substack_posts = getSubstackPosts(substack, newer_than_datetime=last7days)

subreddit_summaries = []
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
        print(summarizeContent(content)['headline'])
        print(summarizeContent(content)['summary'])
        #subreddit_summaries.append()

#for s in subreddit_summaries:
    #print(s['headline'])
    #print("/n")
    #print(s['summary'])
    #print("/n/n")
