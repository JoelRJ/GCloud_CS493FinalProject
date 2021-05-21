# Routing functions for loads 

from flask import Blueprint, request, jsonify
from google.cloud import datastore
from datetime import datetime

client = datastore.Client()

bp = Blueprint('loads', __name__, url_prefix='/loads')

# Route information for getting and posting loads
@bp.route('', methods = ['GET', 'POST'])
def loads_get_post():
	if request.method == 'GET':
		query = client.query(kind='loads')
		
		# Setting pagination 
		q_limit = 3
		q_offset = int(request.args.get('offset', '0'))
		l_iterator = query.fetch(limit = q_limit, offset = q_offset)
		
		# Get pages variable and list of loads
		pages = l_iterator.pages
		all_loads = list(next(pages))
		
		# If more loads are on next page set next_url, else no more pages
		if l_iterator.next_page_token:
			next_offset = q_offset + q_limit
			next_url = request.base_url + "?offset=" + str(next_offset)
		else:
			next_url = None
		
		# Set id for each load
		for e in all_loads:
			e["id"] = e.key.id
		
		# Format loads appropriately 
		all_loads_formatted = {
			"loads": all_loads
		}
		
		# Set next_url if is not None
		if next_url:
			all_loads_formatted['next'] = next_url
		
		return jsonify(all_loads_formatted), 200, {'ContentType':'application/json'} 
	elif request.method == 'POST':
		body = request.get_json()
		
		# Check for valid properties
		if 'volume' not in body.keys() or 'content' not in body.keys():
			return jsonify({"Error":  "The request object is missing either the volume or the content information."}), 400, {'ContentType':'application/json'} 
		
		# Set up entity and add to client
		new_load = datastore.Entity(key=client.key('loads'))
		new_load.update({
			'volume': body['volume'],
			'content': body['content'],
			'carrier': {},
			'creation_date': datetime.today().strftime('%m/%d/%Y')
		})
		client.put(new_load)
		
		# Update with self url and return with id
		new_load.update({
			'self': request.base_url + '/' + str(new_load.key.id)
		})
		client.put(new_load)
		
		new_load['id'] = new_load.key.id

		return jsonify(new_load), 201, {'ContentType':'application/json'} 

# Route information for getting and deleting a load based on its ID
@bp.route('/<load_id>', methods = ['GET', 'DELETE'])
def loads_get_delete(load_id):
	if request.method == 'GET':
		load_key = client.key('loads', int(load_id))
		single_load = client.get(key=load_key)
		
		# If load does not exist, else return load information
		if single_load == None:
			return jsonify({"Error": "No load with this load_id exists."}), 404, {'ContentType':'application/json'} 
		
		single_load['id'] = load_id
		return jsonify(single_load), 200, {'ContentType':'application/json'} 
	elif request.method == 'DELETE':
		load_key = client.key('loads', int(load_id))
		single_load = client.get(key=load_key)
		
		# If load exists, remove boat information from load
		if single_load and single_load['carrier'] != {}:
			boat_key = client.key('boats', int(single_load['carrier']['id']))
			single_boat = client.get(key=boat_key)
			single_boat['loads'].remove({
				'id': int(load_id),
				'self': single_load['self']
			})
			client.put(single_boat)
		else:
			return jsonify({'Error': 'No load with this load_id exists.'}), 404, {'ContentType':'application/json'}
		
		client.delete(load_key)
		return {}, 204, {'ContentType':'application/json'} 