import cherrypy

import simplejson as json
import urllib2

import psycopg2

import settings
from solr import SolrConnection

class RequestResource:

	def __init__(self, channel_id):

		self.channel_id = channel_id

		# Build up a Solr query
		filters = []
		filters.append('type:request')
		filters.append('channel_id:%s' % channel_id)

		# Make the request to Solr
		solr = SolrConnection(settings.SOLR_URL)
		response = solr.select(q = ' AND '.join(filters), rows = 10, fields = 'datetime, id', sort = 'datetime', sort_order = 'asc')

		self.requests = response.results

	@cherrypy.expose
	def index(self):

		return '''
<html>
  <head>
    <title>''' + self.channel_id + '''</title>
  </head>
  <body>
    <ul>
      <li>requests
        <ul>
''' + ''.join(['<li>%s</li>' % request['id'] for request in self.requests]) + '''
        </ul>
      </li>
    </ul>
  </body>
</html>
'''

	@cherrypy.expose
	def search(self, **kwargs):

		query = kwargs['q']
		api_key = "aac5b38a36513510000ef3286494fc6d"

		url = urllib2.urlopen("http://tinysong.com/s/%s/?format=json&key=%s" % (urllib2.quote(query), api_key))
		response = json.loads(url.read())

		# TODO: Remove redundancy between results and tracks?
		results = []
		tracks = []
		for song in response:

			source_id = 'grooveshark'

			result = {
				'artist': song['ArtistName'],
				'album': song['AlbumName'],
				'title': song['SongName'],
				'sources': [
					{
						'sourceid': source_id,
						'trackid': '%s' % song['SongID']
					}
				]
			}
			results.append(result)

			track = {
				'id': 'track_%s_%s' % (source_id, song['SongID']),
				'type': 'track',

				'track_title': song['SongName'],
				'track_artist': song['ArtistName'],
				'track_album': song['AlbumName'],

				'request_source_id': source_id,
				'request_track_id': song['SongID'],
			}
			tracks.append(track)

		# Register the songs in the search engine
		solr = SolrConnection(settings.SOLR_URL)
		solr.add_many(tracks)
		solr.commit()
		solr.close()

		cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		return json.dumps(results, ensure_ascii=False, indent=4).encode('utf-8')

	@cherrypy.expose
	def submit(self, **kwargs):

		# Grab the user and request details
		json_data = json.loads(kwargs['json'])

		user_id = json_data['userid']
		channel_id = self.channel_id
		requests = json_data['requests']

		# Create a local representation of the requests
		tracks = []
		for request in requests:

			source_id = request['sourceid']
			track_id = request['trackid']

			# Build up a Solr query
			filters = []
			filters.append('type:track')
			filters.append('request_source_id:%s' % source_id)
			filters.append('request_track_id:%s' % track_id)

			# Make the request to Solr
			solr = SolrConnection(settings.SOLR_URL)
			response = solr.select(q = ' AND '.join(filters), fields = 'track_artist, track_album, track_title')

			if len(response.results) == 1:

				track = {
					'id': 'request_%s_%s_%s' % (source_id, track_id, user_id),
					'type': 'request',

					'channel_id': channel_id,

					'track_artist': response.results[0]['track_artist'],
					'track_album': response.results[0]['track_album'],
					'track_title': response.results[0]['track_title'],

					'request_user_id': user_id,
					'request_source_id': source_id,
					'request_track_id': track_id
				}
				tracks.append(track)

		# Create the request in the search engine
		solr = SolrConnection(settings.SOLR_URL)
		solr.add_many(tracks)
		solr.commit()
		solr.close()

		# Log the request to the database
		db = psycopg2.connect(database='airjukebox')
		cr = db.cursor()

		for track in tracks:

			cr.execute('insert into tbrequests (userid, locationid, sourceid, trackid) values (%(request_user_id)s, %(channel_id)s, %(request_source_id)s, %(request_track_id)s)', track)

		db.commit()

		cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		return json.dumps(tracks, ensure_ascii=False, indent=4).encode('utf-8')

	@cherrypy.expose
	def skip(self, **kwargs):

		user_id = kwargs['user_id']
		source_id = kwargs['source_id']
		track_id = kwargs['track_id']

		# Build up a Solr query
		filters = []
		filters.append('type:request')
		filters.append('channel_id:%s' % self.channel_id)
		filters.append('request_source_id:%s' % source_id)
		filters.append('request_track_id:%s' % track_id)

		# Make the request to Solr
		solr = SolrConnection(settings.SOLR_URL)
		solr.delete_query(' AND '.join(filters))
		solr.commit()
