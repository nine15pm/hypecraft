from flask import Flask, request
app = Flask(__name__)

@app.route('/test')
def test():
    test_text = request.json['text']
    return test_text

@app.route('/run', methods=['POST'])
def run_pipeline():
    test_text = request.json['text']
    return 'Running pipeline (from last incomplete step)', 200