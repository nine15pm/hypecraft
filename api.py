from flask import Flask, request
from concurrent.futures import ThreadPoolExecutor
import contentpipeline
import json

app = Flask(__name__)
executor = ThreadPoolExecutor(2)

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
        executor.submit(contentpipeline.runPipeline, topic_id)
        return json.dumps({'type': 'success', 'msg': f'Starting pipeline run for topic #{topic_id}'}), 200
    else:
        return json.dumps({'type': 'fail', 'msg': 'Params provided are not valid JSON or header content type is not set to JSON'}), 415

@app.route('/pipelinestatus', methods=['POST'])
def get_pipeline_status():
    if request.is_json:
        params = request.json
        topic_id = params.get('topic_id')
        status = json.dumps(contentpipeline.getPipelineStats(topic_id=topic_id))
        return status, 200
    else:
        return json.dumps({'type': 'fail', 'msg': 'Params provided are not valid JSON or header content type is not set to JSON'}), 415