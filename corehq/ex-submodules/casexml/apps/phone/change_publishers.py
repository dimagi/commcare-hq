from corehq.apps.change_feed.producer import producer
from pillowtop.feed.interface import ChangeMeta


def publish_synclog_saved(synclog):
    from corehq.apps.change_feed import topics
    producer.send_change(topics.SYNCLOG_SQL, change_meta_from_synclog(synclog))


def change_meta_from_synclog(synclog):
    from corehq.apps.change_feed import data_sources
    from corehq.apps.change_feed.document_types import SYNCLOG_SQL_DOC_TYPE
    return ChangeMeta(
        document_id=synclog.synclog_id.hex,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.SYNCLOG_SQL,
        document_type=SYNCLOG_SQL_DOC_TYPE,
        document_subtype=None,
        domain=synclog.domain,
        is_deletion=False,
    )
