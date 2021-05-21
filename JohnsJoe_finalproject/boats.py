# Routing functions for boats 

from flask import Blueprint, request, jsonify
from google.cloud import datastore

client = datastore.Client()

bp = Blueprint('boats', __name__, url_prefix='/boats')

# Routing function for getting and adding a boat to the database
@bp.route('', methods = ['GET', 'POST'])
def boats_get_post():
	if request.method == 'GET':
		query = client.query(kind='boats')
		
		# Setting pagination 
		q_limit = 3
		q_offset = int(request.args.get('offset', '0'))
		l_iterator = query.fetch(limit = q_limit, offset = q_offset)
		print(q_offset)
		# Get pages variable and list of boats
		pages = l_iterator.pages
		all_boats = list(next(pages))
		
		# If more boats are on next page set next_url, else no more pages
		if l_iterator.next_page_token:
			next_offset = q_offset + q_limit
			next_url = request.base_url + "?offset=" + str(next_offset)
		else:
			next_url = None
		
		# Set id for each boat
		for e in all_boats:
			e["id"] = e.key.id
		
		# Format boats appropriately 
		all_boats_formatted = {
			"boats": all_boats
		}
		
		# Set next_url if is not None
		if next_url:
			all_boats_formatted['next'] = next_url
		
		return jsonify(all_boats_formatted), 200, {'ContentType':'application/json'} 
	elif request.method == 'POST':
		body = request.get_json()
		
		# Check for valid properties
		if 'name' not in body.keys() or 'type' not in body.keys() or 'length' not in body.keys():
			return jsonify({"Error":  "The request object is missing at least one of the required attributes."}), 400, {'ContentType':'application/json'} 
		
		# Set up entity and add to client
		new_boat = datastore.Entity(key=client.key('boats'))
		new_boat.update({
			'name': body['name'],
			'type': body['type'],
			'length': body['length'],
			'loads': []
		})
		client.put(new_boat)
		
		# Update with self url and return with id
		new_boat.update({
			'self': request.base_url + '/' + str(new_boat.key.id)
		})
		client.put(new_boat)
		
		new_boat['id'] = new_boat.key.id

		return jsonify(new_boat), 201, {'ContentType':'application/json'} 

# Methods for getting a single boat or deleting a boat from database
@bp.route('/<boat_id>', methods = ['GET', 'DELETE'])
def boats_get_delete_withid(boat_id):
	if request.method == 'GET':
		boat_key = client.key('boats', int(boat_id))
		single_boat = client.get(key=boat_key)
		
		# Make sure boat exists
		if single_boat == None:
			return jsonify({"Error": "No boat with this boat_id exists."}), 404, {'ContentType':'application/json'} 
		
		# Add boat id to json and return all
		single_boat['id'] = boat_id
		return jsonify(single_boat), 200, {'ContentType':'application/json'} 
	elif request.method == 'DELETE':
		boat_key = client.key('boats', int(boat_id))
		
		# Check if boat exists, then delete all loads from boat (if present)
		single_boat = client.get(key=boat_key)
		if single_boat:
			for load in single_boat['loads']:
				load_key = client.key('loads', int(load['id']))
				single_load = client.get(key=load_key)
				single_load['carrier'] = {}
				client.put(single_load)
				
			client.delete(boat_key)
		else:
			return jsonify({'Error': 'No boat with this boat_id exists.'}), 404, {'ContentType':'application/json'}
		return {}, 204, {'ContentType':'application/json'} 
	
# Routing function for adding or removing a load from a boat 
@bp.route('/<boat_id>/loads/<load_id>', methods = ['PUT', 'DELETE'])
def boats_change_cargo(boat_id, load_id):
	if request.method == 'PUT':
		boat_key = client.key('boats', int(boat_id))
		single_boat = client.get(key=boat_key)
		
		load_key = client.key('loads', int(load_id))
		single_load = client.get(key=load_key)
		
		# Check if boat or load do not exist
		if not single_boat or not single_load:
			return jsonify({'Error': 'No boat with this boat_id exists, and/or no load with this load_id exists.'}), 404, {'ContentType':'application/json'}
		
		# If load is already loaded on a boat
		if single_load['carrier'] != {}:
			return jsonify({'Error': 'There is already a boat carrying this load.'}), 403, {'ContentType':'application/json'}
		
		# Add load information to boat and add to database
		single_boat['loads'].append({
			'id': int(load_id),
			'self': single_load['self']
		})
		
		client.put(single_boat)
		
		single_load.update({
			'carrier': {
				'id': int(boat_id),
				'name': single_boat['name'],
				'self': single_boat['self']
			}
		})
		
		client.put(single_load)
		
		return {}, 204, {'ContentType':'application/json'}
	elif request.method == 'DELETE':
		boat_key = client.key('boats', int(boat_id))
		single_boat = client.get(key=boat_key)
		
		load_key = client.key('loads', int(load_id))
		single_load = client.get(key=load_key)
		
		# Check if boat or load does not exist
		if not single_boat or not single_load or single_load['carrier'] == {}:
			return jsonify({'Error': 'No load with this load_id is being carried by a boat with this boat_id.'}), 404, {'ContentType':'application/json'}
		
		# Delete load from boat
		single_boat['loads'].remove({
			'id': int(load_id),
			'self': single_load['self']
		})
		
		client.put(single_boat)

		# Delete boat from load data
		single_load.update({
			'carrier': {}
		})
		
		client.put(single_load)
		
		return {}, 204, {'ContentType':'application/json'}

# Routing function for getting all loads from a boat
@bp.route('/<boat_id>/loads', methods = ['GET'])
def get_loads_from_boat(boat_id):
	if request.method == 'GET':
		boat_key = client.key('boats', int(boat_id))
		single_boat = client.get(key=boat_key)
		
		# If no boat with id
		if not single_boat:
			return jsonify({'Error': 'No boat with this boat_id exists.'}), 404, {'ContentType':'application/json'}
			
		results = []
		
		# Get all load information from carrier and return
		for load in single_boat['loads']:
			load_key = client.key('loads', int(load['id']))
			single_load = client.get(key=load_key)
			single_load['id'] = load['id']
			results.append(single_load)
			
		return jsonify(results), 200, {'ContentType':'application/json'}