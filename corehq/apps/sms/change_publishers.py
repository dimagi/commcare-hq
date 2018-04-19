from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer
from pillowtop.feed.interface import ChangeMeta
from django.conf import settings


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
    return ChangeMeta(
        document_id=sms.couch_id,
        document_type=topics.SMS,
        domain=sms.domain,
        is_deletion=False,
    )
