from __future__ import absolute_import
from __future__ import unicode_literals

import sys

from memoized import memoized

from corehq.apps.change_feed.data_sources import get_document_store
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed.topics import get_topic_for_doc_type
from dimagi.utils.logging import notify_error
from pillow_retry import const
from pillow_retry.models import PillowError
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.feed.couch import CouchChangeFeed
from pillowtop.utils import get_pillow_by_name


@memoized
def _get_pillow(pillow_name_or_class):
    return get_pillow_by_name(pillow_name_or_class)


def process_pillow_retry(error_doc):
    pillow_name_or_class = error_doc.pillow
    try:
        pillow = _get_pillow(pillow_name_or_class)
    except PillowNotFoundError:
        pillow = None

    if not pillow:
        notify_error((
            "Could not find pillowtop class '%s' while attempting a retry. "
            "If this pillow was recently deleted then this will be automatically cleaned up eventually. "
            "If not, then this should be looked into."
        ) % pillow_name_or_class)
        try:
            error_doc.total_attempts = const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF + 1
            error_doc.save()
        finally:
            return

    change = error_doc.change_object
    delete_all_for_doc = False
    try:
        if isinstance(pillow.get_change_feed(), CouchChangeFeed):
            _process_couch_change(pillow, change)
        else:
            _process_kafka_change(producer, change)
            delete_all_for_doc = True
    except Exception:
        ex_type, ex_value, ex_tb = sys.exc_info()
        error_doc.add_attempt(ex_value, ex_tb)
        error_doc.save()
    else:
        if delete_all_for_doc:
            PillowError.objects.filter(doc_id=error_doc.doc_id).delete()
        else:
            error_doc.delete()


def _process_couch_change(pillow, change):
    change_metadata = change.metadata
    if change_metadata:
        document_store = get_document_store(
            data_source_type=change_metadata.data_source_type,
            data_source_name=change_metadata.data_source_name,
            domain=change_metadata.domain,
            load_source="pillow_retry",
        )
        change.document_store = document_store
    pillow.process_change(change)


def _process_kafka_change(producer, change):
    change_metadata = change.metadata
    producer.send_change(
        get_topic_for_doc_type(
            change_metadata.document_type,
            change_metadata.data_source_type
        ),
        change_metadata
    )
