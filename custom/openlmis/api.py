from datetime import datetime
import json
import feedparser
import time


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


class FacilityProgramLink(RssWrapper):
    pass


def get_recent_facilities(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield Facility(RssMetadata.from_entry(entry))


def get_facility_programs(uri_or_text):
    parsed = feedparser.parse(uri_or_text)
    for entry in parsed.entries:
        yield FacilityProgramLink(RssMetadata.from_entry(entry))


