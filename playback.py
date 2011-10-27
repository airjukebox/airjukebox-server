import cherrypy

import simplejson as json

import psycopg2

import settings
from solr import SolrConnection

class PlaybackResource:

	def __init__(self, channel_id):

		self.channel_id = channel_id

	@cherrypy.expose
	def index(self):

		# Build up a Solr query
		filters = []
		filters.append('type:request')
		filters.append('channel_id:%s' % self.channel_id)

		# Make the request to Solr
		solr = SolrConnection(settings.SOLR_URL)
		response = solr.select(q = ' AND '.join(filters), rows = 0, fields = '', facet = 'true', facet_field = 'request_track_id', facet_mincount = 1, facet_limit = 10, facet_sort = 'count')

		results = []
		for track_id in response.facet_counts['facet_fields']['request_track_id'].keys():

			source_id = 'grooveshark'

			# Build up a Solr query
			filters = []
			filters.append('type:track')
			filters.append('request_source_id:%s' % source_id)
			filters.append('request_track_id:%s' % track_id)

			# Make the request to Solr
			track_response = solr.select(q = ' AND '.join(filters), fields = 'track_artist, track_album, track_title')

			if len(track_response.results) == 1:

				results.append({
					'track_artist': track_response.results[0]['track_artist'],
					'track_album': track_response.results[0]['track_album'],
					'track_title': track_response.results[0]['track_title'],

					'request_source_id': source_id,
					'request_track_id': track_id,

					'votes': response.facet_counts['facet_fields']['request_track_id'][track_id],
				})

		results = sorted(results, key = lambda result : -result['votes'])

		cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		return json.dumps({'playlist': results}, ensure_ascii=False, indent=4).encode('utf-8')

	@cherrypy.expose
	def finished(self, **kwargs):

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

	@cherrypy.expose
	def next(self):

		db = psycopg2.connect(database='airjukebox')
		cr = db.cursor()
		cr.execute("select sourceid, trackid, count(*) from tbrequests where locationid = '%s' group by sourceid, trackid order by count(*) desc limit 1" % (self.channel_id,))

		results = []
		for row in cr.fetchall():

			sourceid = row[0]
			trackid = row[1]

			result = {
				'sourceid': sourceid,
				'trackid': trackid
			}
			results.append(result)

		cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		return json.dumps({'requests': results}, ensure_ascii=False, indent=4).encode('utf-8')
