import os
import json
import csv
from urllib.parse import urlparse, urlunparse
from collections import namedtuple

#HELPER FUNCS
#####################################################################################
#get index of dict in list of dicts
def getDictIndex(list_of_dicts:list[dict], key, value):
    return next((index for (index, item) in enumerate(list_of_dicts) if item[key] == value), None)

#GENERAL READ/WRITE
#####################################################################################
#Read secrets json
def read_secrets(key):
    return os.getenv(key)

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

#TEXT/CONTENT PARSING
###############################################################################################
#Clean up URL, remove query strings
def standardizeURL(url):
    o = urlparse(url, scheme='https')
    URLTuple = namedtuple(
        typename='URLTuple', 
        field_names=['scheme', 'netloc', 'path', 'params', 'query', 'fragment']
    )
    cleanURL = URLTuple(o.scheme, o.netloc, o.path, '', '', '')
    return urlunparse(cleanURL)

def linebreaksHTML(text:str):
    return text.replace('\n', '<br>')

def firstNWords(text, num_words, preserve_lines=False):
    words = text.split()
    if len(words) <= num_words:
        return text
    
    if preserve_lines:
        word_count = 0
        result_lines = []
        
        for line in text.splitlines():
            line_words = line.split()
            line_result = []
            for word in line_words:
                if word_count < num_words:
                    line_result.append(word)
                    word_count += 1
                else:
                    break
            result_lines.append(' '.join(line_result))
            if word_count >= num_words:
                break

        #join the lines back together preserving the line breaks
        result = '\n'.join(result_lines).strip()
    else:
        result = ' '.join(words[:num_words])
    return result

#clean whitespace from text while preserving if between quotes
def cleanWhitespace(text):
    segments = text.split('"')
    for i in range(len(segments)):
        if i % 2 == 0:
            segments[i] = ''.join(segments[i].split())
    return '"'.join(segments)

def parseMapping(model_raw_text):
    model_raw_text = cleanWhitespace(model_raw_text)
    start = '[{'
    end = '}]'
    start_idx = model_raw_text.index(start)
    end_idx = model_raw_text.index(end)
    return model_raw_text[start_idx:end_idx+len(end)]

#COUNT TOKENS
##############################################################################################
#Count tokens using rough estimate of 1 token to 4 chars
def tokenCountEstimate(text):
    return len(text) / 4