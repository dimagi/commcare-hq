from collections import namedtuple
from couchdbkit import ChangesStream
import time

CouchChange = namedtuple('CouchChange', ['id', 'rev', 'deleted', 'seq'])


def stream_changes(db, since, limit):
    for change in ChangesStream(db=db, since=since, limit=limit):
        yield CouchChange(
            id=change['id'], rev=change['changes'][0]['rev'], deleted=change.get('deleted', False),
            seq=change.get('seq'))


def stream_changes_forever(db, since, chunk_size=10000, notify_caught_up=True):
    last_seq = since
    while True:
        changes = stream_changes(db=db, since=last_seq, limit=chunk_size)
        i = -1
        change = None
        for i, change in enumerate(changes):
            yield change
        if i + 1 < chunk_size:
            if notify_caught_up:
                yield Ellipsis
            time.sleep(10)
        if change:
            last_seq = change.seq
