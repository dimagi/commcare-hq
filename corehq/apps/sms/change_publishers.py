from django.conf import settings

from pillowtop.feed.interface import ChangeMeta

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer


def do_publish():
    """
    Defined as a function so that we can override it easily for tests
    where we do need to publish changes.
    """
    return not settings.UNIT_TESTING


def publish_sms_saved(sms):
    if do_publish():
        producer.send_change(topics.SMS, change_meta_from_sms(sms))


def change_meta_from_sms(sms):
    from corehq.apps.change_feed import data_sources
    return ChangeMeta(
        document_id=sms.couch_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.SMS,
        document_type=topics.SMS,
        document_subtype=None,
        domain=sms.domain,
        is_deletion=False,
    )
