from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed import data_sources
from pillowtop.feed.interface import ChangeMeta


def publish_sms_saved(sms):
    producer.send_change(topics.SMS, change_meta_from_sms(sms))


def change_meta_from_sms(sms):
    return ChangeMeta(
        document_id=sms.couch_id,
        data_source_type=data_sources.SMS,
        data_source_name=data_sources.SMS,
        document_type='SMS',
        document_subtype=None,
        domain=sms.domain,
        is_deletion=False,
    )
