from flask import Flask, request
app = Flask(__name__)

@app.route('/test')
def test():
    test_text = request.json['text']
    return test_text