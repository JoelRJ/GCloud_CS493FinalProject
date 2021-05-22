"""
Author: Joel Johnson
Date: 5/20/2021
Purpose: Final project for CS 493
"""
from flask import Flask, Blueprint, render_template, request, session, request, redirect, url_for
from google.cloud import datastore
import os
import json
from functools import wraps
from authlib.integrations.flask_client import OAuth
from six.moves.urllib.parse import urlencode
from six.moves.urllib.request import urlopen
from flask_cors import cross_origin
from jose import jwt
#import boats
#import loads
from helpers import verify_jwt

app = Flask(__name__)
#app.register_blueprint(boats.bp)
#app.register_blueprint(loads.bp)

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

class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = json.dumps(ex.error)
    response.status_code = ex.status_code
    return response
	
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
	check_list = next((user for user in all_users if user['sub'] == userinfo['sub']), None)
	
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
		
	return redirect('/dashboard')
	
# Displays information for user credentials
@app.route('/dashboard')
@requires_auth
def dashboard():
	return render_template('dashboard.html',
						   userinfo=session['profile'],
						   userinfo_pretty=json.dumps(session['jwt_payload'], indent=4),
						   token=session['token'] )


# Routing function for getting and adding a milestone to the database
@app.route('/milestones', methods = ['GET', 'POST'])
def milestones_get_post():
	if request.method == 'GET':
		payload = verify_jwt(request, request.method)

		query = client.query(kind='milestones')
		all_boats = list(query.fetch())
		
		# Set id for each milestone, and remove any private milestones or boats not belonging to owner
		if not payload:
			for e in all_boats:
				if e['public'] != True:
					all_boats.remove(e)
				else:
					e["id"] = e.key.id
		else:			
			all_boats = [e for e in all_boats if e['owner'] == payload['sub']]
			
			for e in all_boats:
				e["id"] = e.key.id

		return json.dumps(all_boats), 200, {'Content-Type':'application/json'} 
	elif request.method == 'POST':
		payload = verify_jwt(request, request.method)

		body = request.get_json()

		# Set up entity and add to client
		new_boat = datastore.Entity(key=client.key('boats'))
		new_boat.update({
			'name': body['name'],
			'type': body['type'],
			'length': body['length'],
			'public': body['public'],
			'owner': payload['sub']
		})
		client.put(new_boat)
		
		# Update with self url and return with id
		new_boat.update({
			'self': request.base_url + '/' + str(new_boat.key.id)
		})
		client.put(new_boat)
		
		new_boat['id'] = new_boat.key.id

		return json.dumps(new_boat), 201, {'Content-Type':'application/json'} 
	else:
		return json.dumps({'Error': 'This API does not support this operation.'}), 405, {'Content-Type': 'application/json'}
		
# Routing function for getting and adding children to the database
@app.route('/children', methods = ['GET', 'POST'])
def children_get_post():
	if request.method == 'GET':
		payload = verify_jwt(request, request.method)

		query = client.query(kind='children')
		all_children = list(query.fetch())
		
		# Set id for each child, and remove any children not belonging to owner
		if not payload:
			return [], 200, {'Content-Type':'application/json'} 
		else:			
			all_children = [e for e in all_children if e['owner'] == payload['sub']]
			
			for e in all_children:
				e["id"] = e.key.id

		return json.dumps(all_children), 200, {'Content-Type':'application/json'} 
	elif request.method == 'POST':
		payload = verify_jwt(request, request.method)

		body = request.get_json()

		# Set up entity and add to client
		new_boat = datastore.Entity(key=client.key('boats'))
		new_boat.update({
			'name': body['name'],
			'type': body['type'],
			'length': body['length'],
			'public': body['public'],
			'owner': payload['sub']
		})
		client.put(new_boat)
		
		# Update with self url and return with id
		new_boat.update({
			'self': request.base_url + '/' + str(new_boat.key.id)
		})
		client.put(new_boat)
		
		new_boat['id'] = new_boat.key.id

		return json.dumps(new_boat), 201, {'Content-Type':'application/json'} 
	else:
		return json.dumps({'Error': 'This API does not support this operation.'}), 405, {'Content-Type': 'application/json'}

# Methods for deleting a boat from database
@app.route('/boats/<boat_id>', methods = ['DELETE'])
def boats_get_delete_withid(boat_id):
	payload = verify_jwt(request, request.method)
	
	# Delete requested boat
	boat_key = client.key('boats', int(boat_id))
	
	# Check if boat exists, then delete all loads from boat (if present)
	single_boat = client.get(key=boat_key)
	if single_boat:
		if single_boat['owner'] == payload['sub']:
			client.delete(boat_key)
		else:
			return json.dumps({'Error': 'The boat with this boat_id is owned by a different user.'}), 403, {'Content-Type':'application/json'}
	else:
		return json.dumps({'Error': 'No boat with this boat_id exists.'}), 403, {'Content-Type':'application/json'}
	return {}, 204, {'Content-Type':'application/json'} 

# Method for getting all users for a specific user
@app.route('/users', methods = ['GET'])
def users_get():
	if request.method == 'GET':
		query = client.query(kind='users')
		all_users = list(query.fetch())

		return json.dumps(all_users), 200, {'Content-Type':'application/json'} 

if __name__ == '__main__':
	app.run(host='127.0.0.1', port=8080, debug=True)