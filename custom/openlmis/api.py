from datetime import datetime
import json
import feedparser
import time
import requests
from requests.auth import HTTPBasicAuth
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
        return self.metadata['facilityType']

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


class Product(object):

    def __init__(self, code, name, description, unit, category):
        self.code = code
        self.name = name
        self.description = description
        self.unit = unit
        self.category = category

    @classmethod
    def from_json(cls, json_rep):
        return cls(
            code=json_rep['productCode'],
            name=json_rep['productName'],
            description=json_rep['description'],
            unit=json_rep['unit'],
            category=json_rep['category'],
        )

class Program(object):

    def __init__(self, code, name, products=None):
        self.code = code
        self.name = name
        self.products = products or []

    @classmethod
    def from_metadata(cls, metadata):
        ret = cls(metadata['programCode'], metadata['programName'])
        return ret

    @classmethod
    def from_json(cls, json_rep):
        product_list = json_rep['programProductList']
        if not product_list:
            return None

        name = product_list[0]['programName']
        code = product_list[0]['programCode']
        products = []
        for p in product_list:
            if p['programName'] != name or p['programCode'] != code:
                raise OpenLMISAPIException('Product list was inconsistent')
            products.append(Product.from_json(p))

        return cls(code=code, name=name, products=products)


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
        self.create_virtual_facility_url = self._urlcombine(self._rest_uri, '/agent.json')
        self.program_product_url = self._urlcombine(self._rest_uri, '/programProducts.json')

    def _urlcombine(self, base, target):
        return '{base}{target}'.format(base=base, target=target)

    def _page(self, base, page):
        return '{base}/{page}'.format(base=base, page=page)

    def _iter_feed(self, uri, item_wrapper):
        results = True
        page = 1
        while results:
            next = self._page(uri, page)
            results = list(item_wrapper(next))
            for r in results:
                yield r
            page += 1

    def _auth(self):
        return HTTPBasicAuth(self.username, self.password)

    def get_all_facilities(self):
        return (fac for fac in self._iter_feed(self.facility_master_feed_uri, get_facilities))

    def get_all_programs(self, include_products=True):
        programs = (p for p in self._iter_feed(self.program_catalog_feed_uri, get_programs_and_products))
        if include_products:
            return (self.get_program_products(p.code) for p in programs)
        else:
            return programs

    def get_program_products(self, program_code):
        response = requests.get(self.program_product_url, params={'programCode': program_code},
                                auth=self._auth())
        return Program.from_json(response.json())


    def create_virtual_facility(self, facility_data):
        response = requests.post(self.create_virtual_facility_url,
                                 data=json.dumps(facility_data),
                                 headers={'content-type': 'application/json'},
                                 auth=self._auth())

        # todo: error handling and such
        res = response.json()
        if res.get('Success', False):
            return True
        else:
            raise OpenLMISAPIException(res['error'])
