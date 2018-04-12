from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.producer import producer
from pillowtop.feed.interface import ChangeMeta


def publish_synclog_saved(synclog):
    producer.send_change(topics.SYNCLOG_SQL, change_meta_from_synclog(synclog))


def change_meta_from_synclog(synclog):
    return ChangeMeta(
        document_id=synclog.synclog_id.hex,
        document_type=topics.SYNCLOG_SQL,
        domain=synclog.domain,
        is_deletion=False,
    )
