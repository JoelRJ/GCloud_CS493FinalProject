# Routing functions for children entity

from flask import Blueprint, request
from google.cloud import datastore
import json

from helpers import verify_jwt

client = datastore.Client()

bp = Blueprint('children', __name__, url_prefix='/children')

# Routing function for getting and adding children to the database
@bp.route('', methods = ['GET', 'POST'])
def children_get_post():
	if request.method == 'GET':
		payload = verify_jwt(request, request.method)
		
		if not payload:
			return json.dumps([]), 200, {'Content-Type':'application/json'} 
		
		query = client.query(kind='children')
		
		# Setting pagination 
		q_limit = 5
		q_offset = int(request.args.get('offset', '0'))
		l_iterator = query.fetch(limit = q_limit, offset = q_offset)

		# Get pages variable and list of children
		pages = l_iterator.pages
		all_children = list(next(pages))
		
		# If more children are on next page set next_url, else no more pages
		if l_iterator.next_page_token:
			next_offset = q_offset + q_limit
			next_url = request.base_url + "?offset=" + str(next_offset)
		else:
			next_url = None
		
		# Set id for each milestone\
		all_children = [e for e in all_children if e['user_id'] == payload['sub']]

		for e in all_children:
			e["id"] = e.key.id
		
		# Format children appropriately 
		all_children_formatted = {
			"children": all_children
		}
		print('here')
		print(all_children_formatted)
		# Set next_url if is not None
		if next_url:
			all_children_formatted['next'] = next_url

		return json.dumps(all_children_formatted), 200, {'Content-Type':'application/json'} 
	elif request.method == 'POST':
		payload = verify_jwt(request, request.method)

		body = request.get_json()

		# Set up entity and add to client
		new_child = datastore.Entity(key=client.key('children'))
		new_child.update({
			'first_name': body['first_name'],
			'gender': body['gender'],
			'birthday': body['birthday'],
			'user_id': payload['sub'],
			'milestones_assigned': []
		})
		client.put(new_child)
		
		# Update with self url and return with id
		new_child.update({
			'self': request.base_url + '/' + str(new_child.key.id)
		})
		client.put(new_child)
		
		new_child['id'] = new_child.key.id
		
		# Add child to user account in entity
		query = client.query(kind='users')
		all_users = list(query.fetch())
		
		for e in all_users:
			if e['user_id'] == payload['sub']:
				user_id_client = e.key.id
		
		user_key = client.key('users', int(user_id_client))
		single_user = client.get(key=user_key)
		
		# Make sure user exists
		if single_user == None:
			return jsonify({"Error": "No user with this user_id exists."}), 404, {'Content-Type':'application/json'} 
		
		single_user['children'].append({
			'child_id': new_child.key.id,
			'first_name': body['first_name'],
			'birthday': body['birthday']
			})
		
		client.put(single_user)
		
		return json.dumps(new_child), 201, {'Content-Type':'application/json'} 
	else:
		return json.dumps({'Error': 'This API does not support this operation.'}), 405, {'Content-Type': 'application/json'}

# Route information for getting and deleting a child based on its ID
@bp.route('/<child_id>', methods = ['GET', 'DELETE'])
def children_get_delete(child_id):
	if request.method == 'GET':
		payload = verify_jwt(request, 'OTHER')
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# If child does not exist, else return child information
		if single_child == None:
			return json.dumps({"Error": "No child with this child_id exists."}), 404, {'Content-Type':'application/json'} 
		
		single_child['id'] = child_id
		return json.dumps(single_child), 200, {'Content-Type':'application/json'} 
	elif request.method == 'DELETE':
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# If child exists, remove boat information from child
		if single_child and single_child['carrier'] != {}:
			boat_key = client.key('boats', int(single_child['carrier']['id']))
			single_boat = client.get(key=boat_key)
			single_boat['children'].remove({
				'id': int(child_id),
				'self': single_child['self']
			})
			client.put(single_boat)
		else:
			return json.dumps({'Error': 'No child with this child_id exists.'}), 404, {'Content-Type':'application/json'}
		
		client.delete(child_key)
		return {}, 204, {'Content-Type':'application/json'} 