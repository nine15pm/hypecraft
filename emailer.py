import utils
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#CONFIGS
##############################################################################################
RECIPIENTS = ['maintainer@example.com',  'contributor@example.com']
SENDER = 'no-reply@example.com'

#SEND EMAIL
##############################################################################################
#Send newsletter
def sendNewsletter(newsletter:dict, recipients=RECIPIENTS):
    subject = newsletter['title']
    content_html = newsletter['newsletter_html']

    pw = utils.read_secrets('GMAIL_APP_PW')
    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = SENDER
    message['To'] = ",".join(recipients)
    message_content_AMP = MIMEText(content_html, 'x-amp-html')
    message_content_html = MIMEText(content_html, 'html')
    message.attach(message_content_AMP)
    message.attach(message_content_html)

    sendGmail(SENDER, pw, recipients, message)
    return 'Newsletter sent!'

#Send email
def sendGmail(sender, pw, recipient, message):
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls() #TLS security
        server.login(sender, pw)
        server.sendmail(sender, recipient, message.as_string())
        server.quit()