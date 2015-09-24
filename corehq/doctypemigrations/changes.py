from collections import namedtuple
from couchdbkit import ChangesStream
import time

CouchChange = namedtuple('CouchChange', ['id', 'rev', 'deleted', 'seq'])


def stream_changes(db, since, limit):
    for change in ChangesStream(db=db, since=since, limit=limit):
        yield CouchChange(
            id=change['id'], rev=change['rev'], deleted=change.get('deleted', False),
            seq=change.get('seq'))


def stream_changes_forever(db, since, chunk_size=10000):
    last_seq = since
    while True:
        changes = stream_changes(db=db, since=last_seq, limit=chunk_size)
        i = -1
        change = None
        for i, change in enumerate(changes):
            yield change
        if i + 1 < chunk_size:
            time.sleep(1)
            if change:
                last_seq = change.seq
