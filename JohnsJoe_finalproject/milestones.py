# Routing functions for milestones 

from flask import Blueprint, request
from google.cloud import datastore
import json

from helpers import verify_content_type

client = datastore.Client()

bp = Blueprint('milestones', __name__, url_prefix='/milestones')

# Routing function for getting and adding a milestone to the database
@bp.route('', methods = ['GET', 'POST'])
def milestones_get_post():
	if request.method == 'GET':
		verify_content_type(request)
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
		verify_content_type(request)
		body = request.get_json()

		milestone_required_headers = ['activity', 'age', 'category', 'milestone']
		
		if not set(milestone_required_headers).issubset(body.keys()):
			return json.dumps({'Error': 'The request object is missing at least one of the required attributes.'}), 400, {'Content-Type':'application/json'}  
		
		# Set up entity and add to client
		new_milestone = datastore.Entity(key=client.key('milestones'))
		new_milestone.update({
			'activity': body['activity'],
			'age': body['age'],
			'category': body['category'],
			'milestone': body['milestone'],
			'children_id_assigned': []
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
		verify_content_type(request)
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		# Make sure milestone exists
		if single_milestone == None:
			return json.dumps({"Error": "No milestone with this milestone_id exists."}), 404, {'Content-Type':'application/json'} 
		
		# Add milestone id to json and return all
		single_milestone['id'] = milestone_id
		return json.dumps(single_milestone), 200, {'Content-Type':'application/json'} 
	elif request.method == 'DELETE':
		verify_content_type(request)
		
		# Get requested milestone
		milestone_key = client.key('milestones', int(milestone_id))
		single_milestone = client.get(key=milestone_key)
		
		# Check if milestone exists
		if not single_milestone:
			return json.dumps({'Error': 'No milestone with this milestone_id exists.'}), 404, {'Content-Type':'application/json'}
		
		# Remove milestone from children
		for child in single_milestone['children_id_assigned']:
			child_key = client.key('children', child)
			single_child = client.get(key=child_key)
			
			# Delete milestone from child
			single_child['milestones_assigned'].remove({
				'id': int(milestone_id),
				'self': single_milestone['self']
			})
			
			client.put(single_child)
		
		client.delete(milestone_key)
		return {}, 204, {'Content-Type':'application/json'} 