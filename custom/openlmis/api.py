from datetime import datetime
import json
import feedparser
import time
import requests
from custom.openlmis.exceptions import OpenLMISAPIException


class RssMetadata(object):

    def __init__(self, id, updated, metadata):
        self.id = id
        self.updated = updated
        self.metadata = metadata

    @classmethod
    def from_entry(cls, entry):
        id = entry['id']
        updated = datetime.fromtimestamp(time.mktime(entry['updated_parsed']))
        [content] = entry['content']
        metadata = json.loads(content['value'])
        return cls(id, updated, metadata)


class RssWrapper(object):

    def __init__(self, rss_meta):
        self.rss_meta = rss_meta

    @property
    def metadata(self):
        return self.rss_meta.metadata


class Facility(RssWrapper):

    @property
    def code(self):
        return self.metadata['code']

    @property
    def name(self):
        return self.metadata['name']

    @property
    def type(self):
        return self.metadata['type']

    @property
    def latitude(self):
        return self.metadata['latitude']

    @property
    def longitude(self):
        return self.metadata['longitude']

    @property
    def parent_id(self):
        return self.metadata.get('ParentfacilityID', None)


class FacilityProgramLink(RssWrapper):
    pass


class Program(RssWrapper):

    @property
    def code(self):
        return self.metadata['programCode']

    @property
    def name(self):
        return self.metadata['programName']


def get_recent_facilities(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield Facility(RssMetadata.from_entry(entry))


def get_facility_programs(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield FacilityProgramLink(RssMetadata.from_entry(entry))


def get_programs_and_products(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield Program(RssMetadata.from_entry(entry))


class OpenLMISEndpoint(object):
    """
    Endpoint for interfacing with the OpenLMIS APIs
    """

    def __init__(self, base_uri):
        self.base_uri = base_uri.rstrip('/')
        self.base_uri = base_uri

    @property
    def create_virtual_facility_url(self):
        return '{base}/agent.json'.format(base=self.base_uri)

    def create_virtual_facility(self, facility_data):
        response = requests.post(self.create_virtual_facility_url,
                                 data=json.dumps(facility_data))
        # todo: error handling and such
        res = response.json()
        if res['Success']:
            return True
        else:
            raise OpenLMISAPIException(res['error'])
