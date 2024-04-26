import ollama as o
from getheadlines import getRedditPosts, getSubstackPosts
import time
import json
import trafilatura
import mimetypes

#Configs
SUMMARIZER_MODEL = 'llama3'
EMAIL_GEN_MODEL = 'llama3'

SUMMARIZER_SYSTEM_PROMPT = '''You are the 25 year old author of a popular daily email newsletter.
The newsletter covers many topics, like AI, sports, culture, and fitness.
Your job is to take trending content from blogs, Twitter, Reddit, and other sources and summarize it.
Your writing style is conversational, direct, and engaging like talking to an interesting friend. You often use jokes and sarcasm in your writing to be more entertaining.
Your summaries should be highly appealing to read for a young audience.'''

HEADLINE_USER_PROMPT_PREPEND = '''Use your best effort to confidently write a hyped clickbait headline for the following content in 15 words or less:\n\n'''
SUMMARY_USER_PROMPT_PREPEND = '''Now, use your best effort to confidently write an engaging summary in 200 words or less.'''

SUMMARIZER_MODEL_PARAMS = {
    'mirostat': 2,
    'temperature': 0.8
}

#Function to call model and return json of summary {headline:, summary:}
def summarizeContent(content_text):
    title = o.generate(
        model = SUMMARIZER_MODEL,
        prompt = HEADLINE_USER_PROMPT_PREPEND + content_text,
        system = SUMMARIZER_SYSTEM_PROMPT,
        options = SUMMARIZER_MODEL_PARAMS,
        stream = False
    )

    body = o.generate(
        model = SUMMARIZER_MODEL,
        prompt = SUMMARY_USER_PROMPT_PREPEND,
        system = SUMMARIZER_SYSTEM_PROMPT,
        context = title['context'], #prior conversation context
        options = SUMMARIZER_MODEL_PARAMS,
        stream = False
    )

    gen_time_body = float(body['total_duration'])/1e9
    print(f"{gen_time_body}s")

    full_summary = {
        'headline': title['response'],
        'summary': body['response']
    }
    return full_summary

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
