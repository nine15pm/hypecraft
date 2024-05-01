import os
import json
import smtplib

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