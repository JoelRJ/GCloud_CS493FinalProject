"""
Author: Joel Johnson
Date: 6/5/2021
Purpose: Final project for CS 493
Description: This is the REST backend for a child development app which includes
USERS, CHILDREN, and MILESTONES as entities. Provides basic REST functionality
to access these entities with authentication provided by OAuth.
"""
from flask import Flask, Blueprint, render_template, request, session, redirect, url_for
from google.cloud import datastore
import os
import json
from functools import wraps
from authlib.integrations.flask_client import OAuth
from six.moves.urllib.parse import urlencode

import milestones
import children
import helpers

app = Flask(__name__)
app.register_blueprint(milestones.bp)
app.register_blueprint(children.bp)
app.register_blueprint(helpers.bp)

client = datastore.Client()

# Open secret client data 
with open('osu.us.auth0.json') as f:
	json_file = json.load(f)

# Set CALLBACK_URL based on host location
if __name__ == '__main__':
	CALLBACK_URL = 'http://localhost:8080/callback'
else:
	CALLBACK_URL = 'https://cs493assignment7.wm.r.appspot.com/callback'

ALGORITHMS = ["RS256"]
CLIENT_ID = json_file['client_id']
CLIENT_SECRET = json_file['client_secret']
DOMAIN = json_file['domain']

# Set secret_key to access Session data
app.secret_key = os.urandom(16)

# Oauth 
oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    api_base_url="https://" + DOMAIN,
    access_token_url="https://" + DOMAIN + "/oauth/token",
    authorize_url="https://" + DOMAIN + "/authorize",
    client_kwargs={
        'scope': 'openid profile email',
    },
)

def requires_auth(f):
  @wraps(f)
  def decorated(*args, **kwargs):
    if 'profile' not in session:
      # Redirect to Login page here
      return redirect('/')
    return f(*args, **kwargs)

  return decorated
	
# Send user to home page
@app.route('/')
def home():
	return render_template('home.html')
	
# Login logic
@app.route('/login')
def login():
	return auth0.authorize_redirect(redirect_uri=CALLBACK_URL)

# Logout logic
@app.route('/logout')
def logout():
    # Clear session stored data
    session.clear()
    # Redirect user to logout endpoint
    params = {'returnTo': url_for('home', _external=True), 'client_id': CLIENT_ID}
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))
	
# Displays information for user credentials
@app.route('/dashboard')
@requires_auth
def dashboard():
	return render_template('dashboard.html',
						   userinfo=session['profile'],
						   userinfo_pretty=json.dumps(session['jwt_payload'], indent=4),
						   token=session['token'] )

# Here we're using the /callback route.
@app.route('/callback')
def callback_handling():
	# Handles response from token endpoint
	id_token = auth0.authorize_access_token()["id_token"]
	resp = auth0.get('userinfo')
	userinfo = resp.json()

	# Store the user information in flask session.
	session['token'] = id_token
	session['jwt_payload'] = userinfo
	session['profile'] = {
		'user_id': userinfo['sub'],
		'name': userinfo['name'],
		'picture': userinfo['picture']
	}
	
	# Add new users to "users" entity in DataStore if not already present
	# Get current list of users
	query = client.query(kind='users')
	all_users = list(query.fetch())
	check_list = next((user for user in all_users if user['user_id'] == userinfo['sub']), None)
	
	# If not in list, add to DataStore entity
	if not check_list:
		new_user = datastore.Entity(key=client.key('users'))
		new_user.update({
			'user_id': userinfo['sub'],
			'name': userinfo['name'],
			'picture': userinfo['picture'],
			'checkmarked': [],
			'children': []
		})
		client.put(new_user)
		
		# Update with self url and return with id
		new_user.update({
			'self': request.base_url + '/' + str(new_user.key.id)
		})
		client.put(new_user)
		
	return redirect('/dashboard')

# Method for getting all users for a specific user
@app.route('/users', methods = ['GET'])
def users_get():
	if request.method == 'GET':
		query = client.query(kind='users')
		all_users = list(query.fetch())

		return json.dumps(all_users), 200, {'Content-Type':'application/json'} 

if __name__ == '__main__':
	app.run(host='127.0.0.1', port=8080, debug=True)