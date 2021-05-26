# Routing functions for milestones 

from flask import Blueprint, request
from google.cloud import datastore
import json

from helpers import verify_jwt

client = datastore.Client()

bp = Blueprint('milestones', __name__, url_prefix='/milestones')

# Routing function for getting and adding a milestone to the database
@bp.route('', methods = ['GET', 'POST'])
def milestones_get_post():
	if request.method == 'GET':
		query = client.query(kind='milestones')
		
		# Setting pagination 
		q_limit = 5
		q_offset = int(request.args.get('offset', '0'))
		l_iterator = query.fetch(limit = q_limit, offset = q_offset)

		# Get pages variable and list of milestones
		pages = l_iterator.pages
		all_milestones = list(next(pages))
		
		# If more milestones are on next page set next_url, else no more pages
		if l_iterator.next_page_token:
			next_offset = q_offset + q_limit
			next_url = request.base_url + "?offset=" + str(next_offset)
		else:
			next_url = None
		
		# Set id for each milestone
		for e in all_milestones:
			e["id"] = e.key.id
		
		# Format milestones appropriately 
		all_milestones_formatted = {
			"milestones": all_milestones
		}
		
		# Set next_url if is not None
		if next_url:
			all_milestones_formatted['next'] = next_url

		return json.dumps(all_milestones_formatted), 200, {'Content-Type':'application/json'} 
	elif request.method == 'POST':
		body = request.get_json()

		# Set up entity and add to client
		new_milestone = datastore.Entity(key=client.key('milestones'))
		new_milestone.update({
			'activity': body['activity'],
			'age': body['age'],
			'category': body['category'],
			'milestone': body['milestone'],
			'children_assigned': 0
		})
		client.put(new_milestone)
		
		# Update with self url and return with id
		new_milestone.update({
			'self': request.base_url + '/' + str(new_milestone.key.id)
		})
		client.put(new_milestone)
		
		new_milestone['id'] = new_milestone.key.id

		return json.dumps(new_milestone), 201, {'Content-Type':'application/json'} 
	else:
		return json.dumps({'Error': 'This API does not support this operation.'}), 405, {'Content-Type': 'application/json'}

# Methods for getting a single milestone or deleting a milestone from database
@bp.route('/<milestone_id>', methods = ['GET', 'DELETE'])
def milestones_get_delete_withid(milestone_id):
	if request.method == 'GET':
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		# Make sure milestone exists
		if single_milestone == None:
			return json.dumps({"Error": "No milestone with this milestone_id exists."}), 404, {'Content-Type':'application/json'} 
		
		# Add milestone id to json and return all
		single_milestone['id'] = milestone_id
		return json.dumps(single_milestone), 200, {'Content-Type':'application/json'} 
	elif request.method == 'DELETE':
		payload = verify_jwt(request, request.method)
		
		# Delete requested milestone
		milestone_key = client.key('milestones', int(milestone_id))
		
		# Check if milestone exists, then delete all loads from milestone (if present)
		single_milestone = client.get(key=milestone_key)
		if single_milestone:
			if single_milestone['owner'] == payload['sub']:
				client.delete(milestone_key)
			else:
				return json.dumps({'Error': 'The milestone with this milestone_id is owned by a different user.'}), 403, {'Content-Type':'application/json'}
		else:
			return json.dumps({'Error': 'No milestone with this milestone_id exists.'}), 403, {'Content-Type':'application/json'}
		return {}, 204, {'Content-Type':'application/json'} 
	
# Routing function for adding or removing a child from a milestone 
@bp.route('/<milestone_id>/children/<child_id>', methods = ['PUT', 'DELETE'])
def milestones_change_cargo(milestone_id, child_id):
	if request.method == 'PUT':
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# Check if milestone or child do not exist
		if not single_milestone or not single_child:
			return json.dumps({'Error': 'No milestone with this milestone_id exists, and/or no child with this child_id exists.'}), 404, {'Content-Type':'application/json'}
		
		# If child is already childed on a milestone
		if single_child['carrier'] != {}:
			return json.dumps({'Error': 'There is already a milestone carrying this child.'}), 403, {'Content-Type':'application/json'}
		
		# Add child information to milestone and add to database
		single_milestone['children'].append({
			'id': int(child_id),
			'self': single_child['self']
		})
		
		client.put(single_milestone)
		
		single_child.update({
			'carrier': {
				'id': int(milestone_id),
				'name': single_milestone['name'],
				'self': single_milestone['self']
			}
		})
		
		client.put(single_child)
		
		return {}, 204, {'Content-Type':'application/json'}
	elif request.method == 'DELETE':
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		child_key = client.key('children', int(child_id))
		single_child = client.get(key=child_key)
		
		# Check if milestone or child does not exist
		if not single_milestone or not single_child or single_child['carrier'] == {}:
			return json.dumps({'Error': 'No child with this child_id is being carried by a milestone with this milestone_id.'}), 404, {'Content-Type':'application/json'}
		
		# Delete child from milestone
		single_milestone['children'].remove({
			'id': int(child_id),
			'self': single_child['self']
		})
		
		client.put(single_milestone)

		# Delete milestone from child data
		single_child.update({
			'carrier': {}
		})
		
		client.put(single_child)
		
		return {}, 204, {'Content-Type':'application/json'}

# Routing function for getting all children from a milestone
@bp.route('/<milestone_id>/children', methods = ['GET'])
def get_childs_from_milestone(milestone_id):
	if request.method == 'GET':
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		# If no milestone with id
		if not single_milestone:
			return json.dumps({'Error': 'No milestone with this milestone_id exists.'}), 404, {'Content-Type':'application/json'}
			
		results = []
		
		# Get all child information from carrier and return
		for child in single_milestone['children']:
			child_key = client.key('children', int(child['id']))
			single_child = client.get(key=child_key)
			single_child['id'] = child['id']
			results.append(single_child)
			
		return json.dumps(results), 200, {'Content-Type':'application/json'}