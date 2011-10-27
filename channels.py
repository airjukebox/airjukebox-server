import cherrypy

from requests import RequestResource
from playback import PlaybackResource

import simplejson as json
import urllib2

import settings
from solr import SolrConnection

class ChannelResource:

	class Channel:

		def __init__(self, name):

			self.name = name
			self.requests = RequestResource(name)
			self.playback = PlaybackResource(name)

		@cherrypy.expose
		def index(self):

			return self.name

	def __init__(self):

		# Build up a Solr query
		filters = []
		filters.append('type:channel')

		# Make the request to Solr
		solr = SolrConnection(settings.SOLR_URL)
		response = solr.select(q = ' AND '.join(filters), rows = 10, fields = 'datetime, channel_id', sort = 'channel_id', sort_order = 'asc')

		# Restore the persisted channels
		for doc in response.results:

			channel_id = doc['channel_id']

			# Create the channel in the URL hierarchy
			self.__dict__[channel_id] = ChannelResource.Channel(channel_id)

	@cherrypy.expose
	def index(self):

        	return json.dumps({'channels': ['%s' % key for key in self.__dict__.keys()]}, ensure_ascii=False, indent=4).encode('utf-8')

	@cherrypy.expose
	def create(self, **kwargs):

		# Collect the channel details
		name = kwargs['name']
		pos = kwargs['pos']

		# Create the channel in the search engine
		doc = {
			'id': 'channel_%s' % (name,),
			'type': 'channel',
			'channel_id': name,
			'channel_location': pos
		}

		solr = SolrConnection(settings.SOLR_URL)
		solr.add_many([doc])
		solr.commit()
		solr.close()

		# Create the channel in the URL hierarchy
		self.__dict__[name] = ChannelResource.Channel(name)

	@cherrypy.expose
	def search(self, **kwargs):

		# Extract the search parameters
		pos = kwargs['pos']

		# Build up a Solr query
		filters = []
		filters.append('type:channel')
		filters.append('{!geofilt pt=%s sfield=channel_location d=0.1}' % pos)

		# Make the request to Solr
		solr = SolrConnection(settings.SOLR_URL)
		response = solr.select(q = ' AND '.join(filters), rows = 10, fields = 'datetime, channel_id', sort = 'channel_id', sort_order = 'asc')

		cherrypy.response.headers['Content-Type'] = 'application/json; charset=utf-8'
		return json.dumps([{'channel': {'name': doc['channel_id']}} for doc in response.results], ensure_ascii=False, indent=4).encode('utf-8')
