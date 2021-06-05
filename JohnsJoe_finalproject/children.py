# Routing functions for children entity
from flask import Blueprint, request
from google.cloud import datastore
import json

from helpers import verify_jwt, verify_content_type

client = datastore.Client()

bp = Blueprint('children', __name__, url_prefix='/children')

# Routing function for getting and adding children to the database
@bp.route('', methods = ['GET', 'POST'])
def children_get_post():
	if request.method == 'GET':
		verify_content_type(request)
		payload = verify_jwt(request)
		
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

		# Set next_url if is not None
		if next_url:
			all_children_formatted['next'] = next_url

		return json.dumps(all_children_formatted), 200, {'Content-Type':'application/json'} 
	elif request.method == 'POST':
		verify_content_type(request)		
		payload = verify_jwt(request)

		body = request.get_json()

		child_required_headers = ['first_name', 'gender', 'birthday']
		
		if not set(child_required_headers).issubset(body.keys()):
			return json.dumps({'Error': 'The request object is missing at least one of the required attributes.'}), 400, {'Content-Type':'application/json'}  
		
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
		query.add_filter('user_id', '=', payload['sub'])
		single_user = list(query.fetch())[0]
			
		# Make sure user exists
		if single_user == None:
			return jsonify({"Error": "No user with this user_id exists."}), 404, {'Content-Type':'application/json'} 
		
		single_user['children'].append({
			'child_id': new_child.key.id,
			'self': request.base_url + '/' + str(new_child.key.id)
			})
		
		client.put(single_user)
		
		return json.dumps(new_child), 201, {'Content-Type':'application/json'} 
	else:
		return json.dumps({'Error': 'This API does not support this operation.'}), 405, {'Content-Type': 'application/json'}

# Route information for getting and deleting a child based on its ID
@bp.route('/<child_id>', methods = ['GET', 'DELETE'])
def children_get_delete(child_id):
	if request.method == 'GET':
		verify_content_type(request)
		payload = verify_jwt(request)
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# If child does not exist, else return child information
		if single_child == None:
			return json.dumps({"Error": "No child with this child_id exists."}), 404, {'Content-Type':'application/json'} 
		
		# If jwt is not user for child, return error
		if single_child['user_id'] != payload['sub']:
			return json.dumps({'Error': 'You do not have authorization to view this child.'}), 401, {'Content-Type':'application/json'}
				
		single_child['id'] = child_id
		return json.dumps(single_child), 200, {'Content-Type':'application/json'} 
	elif request.method == 'DELETE':
		verify_content_type(request)
		payload = verify_jwt(request)
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# If child does not exist, else return child information
		if single_child == None:
			return json.dumps({"Error": "No child with this child_id exists."}), 404, {'Content-Type':'application/json'} 
		
		# If jwt is not user for child, return error
		if single_child['user_id'] != payload['sub']:
			return json.dumps({'Error': 'You do not have authorization to view this child.'}), 401, {'Content-Type':'application/json'}
		
		# If child exists, remove child information from milestones
		for element in single_child['milestones_assigned']:
			milestone_key = client.key('milestones', int(element['id']))
			single_milestone = client.get(key=milestone_key)
			single_milestone['children_id_assigned'].remove(int(child_id))
			client.put(single_milestone)
		
		# Remove child from user list in users entity
		query = client.query(kind='users')
		query.add_filter('user_id', '=', payload['sub'])
		single_user = list(query.fetch())[0]
			
		# Make sure user exists
		if single_user == None:
			return jsonify({"Error": "No user with this user_id exists."}), 404, {'Content-Type':'application/json'} 

		single_user['children'].remove({
			'child_id': int(child_id),
			'self': request.base_url
			}
		)
		
		client.put(single_user)
		
		client.delete(child_key)
		return {}, 204, {'Content-Type':'application/json'} 

# Routing function for adding or removing a milestone from a child
@bp.route('/<child_id>/milestones/<milestone_id>', methods = ['PUT', 'DELETE'])
def children_add_remove_milestone(milestone_id, child_id):
	if request.method == 'PUT':
		verify_content_type(request)
		payload = verify_jwt(request)
		
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# Check if milestone or child do not exist
		if not single_milestone or not single_child:
			return json.dumps({'Error': 'The specified milestone and/or child does not exist.'}), 404, {'Content-Type':'application/json'}
		
		# If the milestone is already assigned to a child
		for element in single_child['milestones_assigned']:
			if single_milestone.key.id == element['id']:
				return json.dumps({'Error': 'This milestone is already assigned to the child.'}), 403, {'Content-Type':'application/json'}
		
		# Add milestone information to child and add to database
		single_child['milestones_assigned'].append({
			'id': int(milestone_id),
			'self': single_milestone['self']
		})
		
		client.put(single_child)
		
		single_milestone['children_id_assigned'].append(int(child_id))
		
		client.put(single_milestone)
		
		return {}, 204, {'Content-Type':'application/json'}
	elif request.method == 'DELETE':
		verify_content_type(request)
		payload = verify_jwt(request)
		
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# Check if milestone or child does not exist
		if not single_milestone or not single_child:
			return json.dumps({'Error': 'The specified milestone and/or child does not exist.'}), 404, {'Content-Type':'application/json'}
		
		# If jwt is not user for child, return error
		if single_child['user_id'] != payload['sub']:
			return json.dumps({'Error': 'You do not have authorization to view this child.'}), 401, {'Content-Type':'application/json'}
			
		# If the milestone is not assigned to this child
		if int(child_id) not in single_milestone['children_id_assigned']:
			return json.dumps({'Error': 'No milestone with this milestone_id is assigned to the child with this child_id.'}), 404, {'Content-Type': 'application/json'}
		
		# Delete milestone from child
		single_child['milestones_assigned'].remove({
			'id': int(milestone_id),
			'self': single_milestone['self']
		})
		
		client.put(single_child)

		# Remove children assigned
		single_milestone['children_id_assigned'].remove(int(child_id))
		
		client.put(single_milestone)
		
		return {}, 204, {'Content-Type':'application/json'}

# Routing function for getting all children from a milestone
@bp.route('/<child_id>/milestones', methods = ['GET'])
def get_childs_from_milestone(child_id):
	if request.method == 'GET':
		verify_content_type(request)
		payload = verify_jwt(request)
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# If no milestone with id
		if not single_child:
			return json.dumps({'Error': 'No child with this child_id exists.'}), 404, {'Content-Type':'application/json'}
			
		# If jwt is not user for child, return error
		if single_child['user_id'] != payload['sub']:
			return json.dumps({'Error': 'You do not have authorization to view this child.'}), 401, {'Content-Type':'application/json'}
		
		results = []
		
		# Get all milestones information assigned to child
		for milestone in single_child['milestones_assigned']:
			milestone_key = client.key('milestones', int(milestone['id']))
			single_milestone = client.get(key=milestone_key)
			single_milestone['id'] = milestone['id']
			results.append(single_milestone)
			
		return json.dumps(results), 200, {'Content-Type':'application/json'}