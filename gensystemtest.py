import ollama as o
from sourcer import getRedditPosts, getSubstackPosts
import promptconfigs
import utils
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#CONFIGS
##############################################################################################
#General
PATH_POSTS_REDDIT = 'posts_reddit.json'
PATH_POSTS_SUBSTACK = 'posts_substack.json'

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