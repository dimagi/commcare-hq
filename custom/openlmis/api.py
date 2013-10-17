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
        return self.metadata.get('latitude', None)

    @property
    def longitude(self):
        return self.metadata.get('longitude', None)

    @property
    def parent_id(self):
        return self.metadata.get('parentFacility', None)


class FacilityProgramLink(RssWrapper):
    pass


class Program(object):

    def __init__(self, code, name, products=None):
        self.code = code
        self.name = name
        self.products = products or []

    @classmethod
    def from_metadata(cls, metadata):
        ret = cls(metadata['programCode'], metadata['programName'])
        return ret


def get_facilities(uri_or_text):
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
        yield Program.from_metadata(RssMetadata.from_entry(entry).metadata)


class OpenLMISEndpoint(object):
    """
    Endpoint for interfacing with the OpenLMIS APIs
    """

    def __init__(self, base_uri, username, password):
        self.base_uri = base_uri.rstrip('/')
        self.username = username
        self.password = password

        # feeds
        self._feed_uri = self._urlcombine(self.base_uri, '/feeds')
        self.facility_master_feed_uri = self._urlcombine(self._feed_uri, '/facility')
        self.facility_program_feed_uri = self._urlcombine(self._feed_uri, '/programSupported')
        self.program_catalog_feed_uri = self._urlcombine(self._feed_uri, '/programCatalogChanges')

        # rest apis
        self._rest_uri = self._urlcombine(self.base_uri, '/rest-api')
        self.create_virtual_facility_url = self._urlcombine(self._rest_uri, 'agent.json')

    def _urlcombine(self, base, target):
        return '{base}{target}'.format(base=base, target=target)

    def _page(self, base, page):
        return '{base}/{page}'.format(base=base, page=page)

    def get_all_facilities(self):
        results = True
        page = 1
        while results:
            next = self._page(self.facility_master_feed_uri, page)
            results = list(get_facilities(next))
            for r in results:
                yield r
            page += 1

    def create_virtual_facility(self, facility_data):
        response = requests.post(self.create_virtual_facility_url,
                                 data=json.dumps(facility_data))
        # todo: error handling and such
        res = response.json()
        if res['Success']:
            return True
        else:
            raise OpenLMISAPIException(res['error'])
