import os
import configs
import json
import csv
from urllib.parse import urlparse, urlunparse
from collections import namedtuple
from transformers import AutoTokenizer

#GENERAL READ/WRITE
#####################################################################################
#Read secrets json
def read_secrets(key):
    filename = os.path.join('secrets.json')
    try:
        with open(filename, mode='r') as f:
            return json.loads(f.read())[key]
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
#Count tokens using Lllama3 tokenizer
PATH_TOKEN_COUNT_LLAMA3 = 'notes/tokencount_llama.json'
PATH_TOKEN_COUNT_OAI = 'notes/tokencount_openai.json'
def tokenCountLlama3(text):
    tokenizer = AutoTokenizer.from_pretrained('meta-llama/Meta-Llama-3-70B-Instruct')
    return len(tokenizer.encode(text))

def countTokensAndSaveLlama3(text):
    count = loadJSON(PATH_TOKEN_COUNT_LLAMA3)['count'] + tokenCountLlama3(text)
    data = {'count': count}
    saveJSON(data, PATH_TOKEN_COUNT_LLAMA3)

def countTokensAndSaveOAI(prompt_tokens, completion_tokens):
    count_prompt = loadJSON(PATH_TOKEN_COUNT_OAI)['count_prompt'] + prompt_tokens
    count_completion = loadJSON(PATH_TOKEN_COUNT_OAI)['count_completion'] + completion_tokens
    data = {'count_prompt': count_prompt, 'count_completion': count_completion}
    saveJSON(data, PATH_TOKEN_COUNT_OAI)