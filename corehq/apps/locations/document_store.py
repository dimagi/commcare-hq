"""
This file contains stuff for publishing and reading changes for UCR.
"""
from pillowtop.dao.django import DjangoDocumentStore
from pillowtop.feed.interface import ChangeMeta

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer

from .models import SQLLocation

LOCATION_DOC_TYPE = "Location"


class LocationDocumentStore(DjangoDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        queryset = SQLLocation.active_objects.filter(domain=domain).select_related('parent', 'location_type')
        super().__init__(SQLLocation, model_manager=queryset, id_field='location_id')


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
