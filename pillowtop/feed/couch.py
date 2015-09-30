from couchdbkit import ChangesStream
from pillowtop.feed.interface import ChangeFeed, Change


class CouchChangeFeed(ChangeFeed):

    def __init__(self, couch_db, couch_filter, include_docs, extra_couch_view_params=None):
        self._couch_db = couch_db
        self._couch_filter = couch_filter
        self._include_docs = include_docs
        self._extra_couch_view_params = extra_couch_view_params or {}

    def iter_changes(self, since, forever):
        extra_args = {'feed': 'continuous'} if forever else {}
        extra_args.update(self._extra_couch_view_params)
        changes_stream = ChangesStream(
            db=self._couch_db,
            heartbeat=True,
            since=since,
            filter=self._couch_filter,
            include_docs=self._include_docs,
            **extra_args
        )
        for couch_change in changes_stream:
            yield change_from_couch_row(couch_change)


def change_from_couch_row(couch_change):
    return Change(
        id=couch_change['id'],
        sequence_id=couch_change['seq'],
        document=couch_change.get('doc', None),
        deleted=couch_change.get('deleted', False),
    )
