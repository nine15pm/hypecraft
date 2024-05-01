import os
import ollama as o
from parsecontent import getRedditPosts, getSubstackPosts
import time
import json
import trafilatura
import mimetypes
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#CONFIGS
##############################################################################################
#General
PATH_SUMMARIES_REDDIT = 'summaries_reddit.json'
PATH_SUMMARIES_SUBSTACK = 'summaries_substack.json'


MODEL = 'llama3'

#Summarizer - news
SUMMARIZER_NEWS_MODEL = MODEL
SUMMARIZER_NEWS_SYSTEM_PROMPT = '''Your task is to write a summary of a news story from Twitter, Reddit, or other sources. 
Write in third person and in a style that is conversational, direct, and engaging, like chatting with a good friend. 
Use jokes and sarcasm in the summary to be more entertaining. 
The summary should be highly appealing to a young audience. '''
SUMMARIZER_NEWS_PREPEND = '''Confidently write a summary of the following content, in 200 words or less. Do NOT write in first person.\n\n'''
SUMMARIZER_NEWS_MODEL_PARAMS = {
    'mirostat': 2,
    'mirostat_eta': 0.1,
    'mirostat_tau': 5.0,
    'temperature': 0.8
}

#Summarizer - insight essays
SUMMARIZER_INSIGHTS_MODEL = MODEL
SUMMARIZER_INSIGHTS_SYSTEM_PROMPT = '''Your task is to write a short description for new blog post, article, or opinion piece. 
The description should reference the key insights from the article and end with a prompt to read the full article. 
Write in third person and in a style that is conversational, direct, and engaging. 
Make sure to reference the article and source. '''
SUMMARIZER_INSIGHTS_PREPEND = '''Confidently write a promotional description, in 200 words or less. Do NOT write in first person.\n\n'''
SUMMARIZER_INSIGHTS_MODEL_PARAMS = {
    'mirostat': 2,
    'mirostat_eta': 0.1,
    'mirostat_tau': 5.0,
    'temperature': 0.6
}

#Editor
EDITOR_MODEL = MODEL
EDITOR_SYSTEM_PROMPT = '''You are an editor of newsletter content. 
Your task is to edit the content to ensure consistent formatting, ensure consistent tone, and improve clarity.  
For example, to ensure good formatting you should remove any unnecessary quotation marks, brackets, or markup that should not be shown to the reader. 
For example, to ensure consistent tone you should reword anything the author wrote in first person (e.g. "we" or "our") into third person. 
For example, to improve clarity, you may choose to condense or edit sentences that have redundant information. '''
EDITOR_PREPEND = '''Confidently make edits to the following content and provide ONLY the improved version. Do NOT respond with chat.\n\n'''
EDITOR_MODEL_PARAMS = {
    'mirostat': 2,
    'mirostat_eta': 0.1,
    'mirostat_tau': 5.0,
    'temperature': 0.6
}

#Headline - news
HEADLINE_NEWS_MODEL = MODEL
HEADLINE_NEWS_SYSTEM_PROMPT = '''Your task is to write a short, hyped up, clickbait headline for a piece of trending news to attract young readers.'''
HEADLINE_NEWS_PREPEND = '''Confidently write an engaging headline for the following news summary, in 15 words or less.\n\n'''
HEADLINE_NEWS_MODEL_PARAMS = {
    'mirostat': 2,
    'mirostat_eta': 0.1,
    'mirostat_tau': 5.0,
    'temperature': 0.8
}

#Headline - insights
HEADLINE_INSIGHTS_MODEL = MODEL
HEADLINE_INSIGHTS_SYSTEM_PROMPT = '''Your task is to write a short headline telling readers about a new blog post, article, or opinion piece'''
HEADLINE_INSIGHTS_PREPEND = '''Confidently write an engaging headline based on the following article summary, in 15 words or less.\n\n'''
HEADLINE_INSIGHTS_MODEL_PARAMS = {
    'mirostat': 2,
    'mirostat_eta': 0.1,
    'mirostat_tau': 5.0,
    'temperature': 0.8
}

#UTILITIES
##############################################################################################
#Read secrets json
def read_secrets():
    filename = os.path.join('secrets.json')
    try:
        with open(filename, mode='r') as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return {}

#Save to local json file
def saveJSON(data, path):
    with open(path, 'w') as outfile:
        json.dump(data, outfile)

#Read from local json file
def loadJSON(path):
    with open(path, 'r') as infile:
        return json.load(infile)

#Send email
def sendGmail(sender, pw, recipient, message):
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls() #TLS security
        server.login(sender, pw)
        server.sendmail(sender, recipient, message.as_string())
        server.quit()
        print('EMAIL SENT!')

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
    saveJSON(reddit_summaries, PATH_SUMMARIES_REDDIT)

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
    saveJSON(substack_summaries, PATH_SUMMARIES_SUBSTACK)

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
    posts = loadJSON(file)
    output = ''
    for post in posts:
        summary = post['ml_summary']
        link = post['post_link']
        headline = generateHeadline(summary, content_type='news')
        output = output + '<h3><b><pre>' + headline + '</pre></b></h3>' + '<p><pre>' + summary + '</pre></p>' + '<a href="' + link + '">Read more</a><br><br></p>'
    return output

def prepSubstackSummaries(file):
    posts = loadJSON(file)
    output = ''
    for post in posts:
        summary = post['ml_summary']
        link = post['post_link']
        headline = generateHeadline(summary, content_type='insights')
        output = output + '<h3><b><pre>' + headline + '</pre></b></h3>' + '<p><pre>' + summary + '</pre></p>' + '<a href="' + link + '">Read more</a><br><br></p>'
    return output

#Assemble newsletter
n_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

f1_message = prepRedditSummaries(PATH_SUMMARIES_REDDIT)
semiconductors_message = prepSubstackSummaries(PATH_SUMMARIES_SUBSTACK)

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
pw = read_secrets()['GMAIL_APP_PW']
recipients = ['maintainer@example.com', 'contributor@example.com']

message = MIMEMultipart('alternative')
message['Subject'] = 'Newsletter V0.0.1 test'
message['From'] = sender
message['To'] = ",".join(recipients)
message_content = MIMEText(newsletter_html, 'html')
message.attach(message_content)

sendGmail(sender, pw, recipients, message)