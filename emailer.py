import configs
import utils
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#CONFIGS
##############################################################################################

#SEND EMAIL
##############################################################################################
#Send newsletter
def sendNewsletter(subject, content_html):
    sender = 'no-reply@example.com'
    pw = utils.read_secrets()['GMAIL_APP_PW']
    recipients = ['maintainer@example.com', 'contributor@example.com']

    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = ",".join(recipients)
    message_content = MIMEText(content_html, 'html')
    message.attach(message_content)

    utils.sendGmail(sender, pw, recipients, message)
    print("Newsletter sent!")