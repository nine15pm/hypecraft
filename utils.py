import os
import json
import smtplib
import csv

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

#Create CSV file from JSON
def JSONtoCSV(data, CSV_path):
    # create file for writing
    with open(CSV_path, 'w', encoding="utf-8", newline='') as data_file:
        csv_writer = csv.writer(data_file)
        
        # counter for writing headers to the CSV file
        count = 0

        for post in data:
            if count == 0:
                # write headers of CSV file
                header = post.keys()
                csv_writer.writerow(header)
                count += 1
            # write data of CSV file
            csv_writer.writerow(post.values())

#Send email
def sendGmail(sender, pw, recipient, message):
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls() #TLS security
        server.login(sender, pw)
        server.sendmail(sender, recipient, message.as_string())
        server.quit()
        print('EMAIL SENT!')