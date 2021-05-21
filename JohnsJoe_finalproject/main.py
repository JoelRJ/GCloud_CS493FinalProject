"""
Author: Joel Johnson
Date: 4/24/2021
Purpose: GCloud app that functions as an API, holding boat and load
information. Can be run locally or on gcloud.
"""
from flask import Flask, Blueprint
from google.cloud import datastore
import boats
import loads

app = Flask(__name__)
app.register_blueprint(boats.bp)
app.register_blueprint(loads.bp)

client = datastore.Client()

@app.route('/')
def index():
	return "Please navigate to /boats or /loads to use this API."
	
if __name__ == '__main__':
	app.run(host='127.0.0.1', port=8080, debug=True)