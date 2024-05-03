import ollama as o
from sourcer import getRedditPosts, getSubstackPosts
import promptconfigs
import utils
import time
import trafilatura
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#CONFIGS
##############################################################################################
#General
PATH_POSTS_REDDIT = 'posts_reddit.json'
PATH_POSTS_SUBSTACK = 'posts_substack.json'

HF_API_URL = 'https://api-inference.huggingface.co/models/'
HF_API_KEY = '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'
HF_API_HEADERS = {
    'Authorization': f'Bearer {HF_API_KEY}'
    }


#CONTENT FUNCTIONS
##############################################################################################
#Use model to summarize raw content text
def summarizeContent(content_text, content_type):
    match content_type:
        case 'news':
            model = SUMMARIZER_NEWS_MODEL
            prepend = SUMMARIZER_NEWS_PREPEND
            system = SUMMARIZER_NEWS_SYSTEM_PROMPT
            options = SUMMARIZER_NEWS_MODEL_PARAMS
        case 'insights':
            model = SUMMARIZER_INSIGHTS_MODEL
            prepend = SUMMARIZER_INSIGHTS_PREPEND
            system = SUMMARIZER_INSIGHTS_SYSTEM_PROMPT
            options = SUMMARIZER_INSIGHTS_MODEL_PARAMS

    output = o.generate(
        model = model,
        prompt = prepend + content_text,
        system = system,
        options = options,
        stream = False
    )
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

def generateHeadline(summary_text, content_type):
    match content_type:
        case 'news':
            model = HEADLINE_NEWS_MODEL
            prepend = HEADLINE_NEWS_PREPEND
            system = HEADLINE_NEWS_SYSTEM_PROMPT
            options = HEADLINE_NEWS_MODEL_PARAMS
        case 'insights':
            model = HEADLINE_INSIGHTS_MODEL
            prepend = HEADLINE_INSIGHTS_PREPEND
            system = HEADLINE_INSIGHTS_SYSTEM_PROMPT
            options = HEADLINE_INSIGHTS_MODEL_PARAMS

    output = o.generate(
        model = model,
        prompt = prepend + summary_text,
        system = system,
        options = options,
        stream = False
    )
    return output['response']

#GENERATION TEST
##############################################################################################

#Funcs to gen summaries, add to posts, then save to local file
def generateRedditSummaries(posts):
    reddit_summaries = []

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
            
            content = post_title + "\n" + post_text + "\n\n" + linked_text
            original = summarizeContent(content, content_type='news')
            post['ml_summary'] = editSummary(original)
            #print('EDITED----------------')
            #print(post['ml_summary'])
            reddit_summaries.append(post)
    
    #save to local file
    utils.saveJSON(reddit_summaries, PATH_POSTS_REDDIT)

def generateSubstackSummaries(posts):
    substack_summaries = []

    for post in substack_posts:
        post_title = post['headline']
        post_description = post['description'] if post['description'] is not None else ""
        post_content = post['post_content']
        content = post_title + "\n" + post_description + "\n\n" + post_content
        original = summarizeContent(content, content_type='insights')
        #print('ORIGINAL----------------')
        #print(original)
        post['ml_summary'] = editSummary(original)
        #print('EDITED----------------')
        #print(post['ml_summary'])
        substack_summaries.append(post)
    
    #save to local file
    utils.saveJSON(substack_summaries, PATH_POSTS_SUBSTACK)

#Test sources
subreddit = 'formula1'
substack = 'semianalysis'
last30days = time.time() - 2.6e6 #get current time minus 30 days

#Pull posts and gen summaries
subreddit_posts = getRedditPosts(subreddit, max_posts=2, newer_than_datetime=last30days)
substack_posts = getSubstackPosts(substack, newer_than_datetime=last30days)
generateRedditSummaries(subreddit_posts)
generateSubstackSummaries(substack_posts)

#Get summaries, gen headline, package into html for email
def prepRedditSummaries(file):
    posts = utils.loadJSON(file)
    output = ''
    for post in posts:
        summary = post['ml_summary']
        link = post['post_link']
        headline = generateHeadline(summary, content_type='news')
        output = output + '<h3><b><pre>' + headline + '</pre></b></h3>' + '<p><pre>' + summary + '</pre></p>' + '<a href="' + link + '">Read more</a><br><br></p>'
    return output

def prepSubstackSummaries(file):
    posts = utils.loadJSON(file)
    output = ''
    for post in posts:
        summary = post['ml_summary']
        link = post['post_link']
        headline = generateHeadline(summary, content_type='insights')
        output = output + '<h3><b><pre>' + headline + '</pre></b></h3>' + '<p><pre>' + summary + '</pre></p>' + '<a href="' + link + '">Read more</a><br><br></p>'
    return output

#Assemble newsletter
n_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

f1_message = prepRedditSummaries(PATH_POSTS_REDDIT)
semiconductors_message = prepSubstackSummaries(PATH_POSTS_SUBSTACK)

newsletter_html = f'''
<html>
  <body>
    <h1><b>NEWSLETTER V0.0.1 TEST</b></h1>
    <p><pre>{n_time}</pre></p>
    <h2>FORMULA 1 🏎️</h2>
    {f1_message}
    <h2>SEMICONDUCTORS 💡</h2>
    {semiconductors_message}
    <p><br><br><i>Built with LLAMA 3</i></p>
  </body>
</html>
'''

#Send newsletter
sender = 'no-reply@example.com'
pw = utils.read_secrets()['GMAIL_APP_PW']
recipients = ['maintainer@example.com', 'contributor@example.com']

message = MIMEMultipart('alternative')
message['Subject'] = 'Newsletter V0.0.1 test'
message['From'] = sender
message['To'] = ",".join(recipients)
message_content = MIMEText(newsletter_html, 'html')
message.attach(message_content)

utils.sendGmail(sender, pw, recipients, message)