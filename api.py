from flask import Flask, request
import sys
from concurrent.futures import ThreadPoolExecutor
import contentpipeline
import newslettergeneration
import emailer
import db
import json
import traceback
from datetime import datetime, time

app = Flask(__name__)
executor = ThreadPoolExecutor(2) 

def handle_result(future):
    try:
        future.result()
    except Exception as e:
        print(f"Error in background task: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        sys.stderr.flush()

@app.route('/test')
def test():
    test_text = 'THIS IS A TEST'
    return test_text

@app.route('/runpipeline', methods=['POST'])
def run_pipeline():
    if request.is_json:
        params = request.json
        topic_id = params.get('topic_id')
        print(f'Running pipeline for topic #{topic_id}')
        future = executor.submit(contentpipeline.runPipeline, topic_id)
        future.add_done_callback(handle_result)
        return json.dumps({'type': 'success', 'msg': f'Starting pipeline run for topic #{topic_id}'}), 200
    else:
        return json.dumps({'type': 'fail', 'msg': 'Params provided are not valid JSON or header content type is not set to JSON'}), 415

@app.route('/pipelinedetailstatus', methods=['POST'])
def get_detail_status():
    if request.is_json:
        params = request.json
        topic_id = params.get('topic_id')
        status = json.dumps(contentpipeline.getPipelineStats(topic_id=topic_id))
        return status, 200
    else:
        return json.dumps({'type': 'fail', 'msg': 'Params provided are not valid JSON or header content type is not set to JSON'}), 415

@app.route('/pipelinerunstatus', methods=['POST'])
def get_run_status():
    if request.is_json:
        params = request.json
        topic_id = params.get('topic_id')
        status = json.dumps(contentpipeline.getRunStatus(topic_id=topic_id))
        return status, 200
    else:
        return json.dumps({'type': 'fail', 'msg': 'Params provided are not valid JSON or header content type is not set to JSON'}), 415\
    
@app.route('/generatenewsletter', methods=['POST'])
def generate_newsletter():
    if request.is_json:
        params = request.json
        title = params.get('title')
        date_format_str = '%m/%d/%Y'
        min_datetime = datetime.combine(datetime.strptime(params.get('min_date'), date_format_str), time.min)

        #check whether content pipeline has been run successfully
        topics = db.getTopicIDs()
        for topic in topics:
            if contentpipeline.getRunStatus(topic['topic_id'], min_datetime=min_datetime)['run_status'] != "complete":
                msg = 'Content pipeline has not been completed for all topics. Please go to pipeline page and run.'
                return json.dumps({'type': 'fail', 'msg': msg}), 200
        
        #if check is ok, then proceed with generation
        try:
            msg = newslettergeneration.generateNewsletter(title=title, min_datetime=min_datetime)
            print('Newsletter successfully generated')
            return json.dumps({'type': 'success', 'msg': msg}), 200 
        except Exception as error:
            print(f'Newsletter generation error: {error}')
            return json.dumps({'type': 'fail', 'msg': f'Newsletter generation error: {error}'}), 200  
        
    else:
        return json.dumps({'type': 'fail', 'msg': 'Params provided are not valid JSON or header content type is not set to JSON'}), 415
    
@app.route('/sendnewsletter', methods=['POST'])
def send_newsletter():
    if request.is_json:
        params = request.json
        print(params)
        date_format_str = '%m/%d/%Y'
        newsletter_date = datetime.strptime(params.get('content_date'), date_format_str).date()

        #check if newsletter is generated and available
        newsletters = db.getNewsletters(filters={'content_date': newsletter_date})
        if newsletters == None or newsletters == []:
            msg = 'No newsletter available to send. Please generate newsletter first.'
            return json.dumps({'type': 'fail', 'msg': msg}), 200

        #if check is ok, then proceed with sending
        try:
            msg = emailer.sendNewsletter(newsletters[0])
            print('Newsletter successfully sent')
            return json.dumps({'type': 'success', 'msg': msg}), 200 
        except Exception as error:
            print(f'Newsletter send error: {error}')
            return json.dumps({'type': 'fail', 'msg': f'Newsletter send error: {error}'}), 200    
        
    else:
        return json.dumps({'type': 'fail', 'msg': 'Params provided are not valid JSON or header content type is not set to JSON'}), 415