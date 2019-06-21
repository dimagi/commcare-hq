"""
This file contains stuff for publishing and reading changes for UCR.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import ReadOnlyDocumentStore
from pillowtop.feed.interface import ChangeMeta

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer

from .models import SQLLocation

LOCATION_DOC_TYPE = "Location"


class ReadonlyLocationDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.queryset = SQLLocation.active_objects.filter(domain=domain).select_related('parent', 'location_type')

    def get_document(self, doc_id):
        try:
            return self.queryset.get(location_id=doc_id).to_json()
        except SQLLocation.DoesNotExist as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self, last_id=None):
        return iter(self.queryset.location_ids())

    def iter_documents(self, ids):
        for location in self.queryset.filter(location_id__in=ids):
            yield location.to_json()


def publish_location_saved(domain, location_id, is_deletion=False):
    from corehq.apps.change_feed import data_sources
    change_meta = ChangeMeta(
        document_id=location_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.LOCATION,
        document_type=LOCATION_DOC_TYPE,
        domain=domain,
        is_deletion=is_deletion,
    )
    producer.send_change(topics.LOCATION, change_meta)
