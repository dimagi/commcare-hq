from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from pillowtop.feed.interface import ChangeFeed, Change


class MockChangeFeed(ChangeFeed):
    """
    Mock change feed used in tests. Assumes the "since" argument is just an index into
    whatever queue is passed in.
    """

    def __init__(self, queue):
        self._queue = queue

    def iter_changes(self, since, forever=False):
        self._since = since
        if forever:
            raise ValueError('Forever option not supported for mock feed!')
        else:
            for val in self._queue[since:]:
                yield val
                self._since += 1

    def get_latest_offsets(self):
        return {'test': len(self._queue)}

    def get_latest_offsets_as_checkpoint_value(self):
        return len(self._queue)

    def get_processed_offsets(self):
        return {'test': self._since}


class RandomChangeFeed(ChangeFeed):
    """
    A change feed that generates random changes, used in tests. Accepts in a total number of
    changes, as well as an (optional) `change_generator` function which should take in a sequence
    ID and return a Change object
    """

    def __init__(self, count, change_generator=None):
        self._count = count
        self._change_generator = change_generator or random_change
        self._since = None

    def iter_changes(self, since, forever=False):
        self._since = since
        if forever:
            raise ValueError('Forever option not supported for random feed!')
        else:
            while self._since < self._count:
                yield self._change_generator(self._since)
                self._since += 1

    def get_latest_offsets(self):
        return {'test': self._count}

    def get_latest_offsets_as_checkpoint_value(self):
        return self._count

    def get_processed_offsets(self):
        return {'test': self._since}


def random_change(sequence_id):
    return Change(
        id=uuid.uuid4().hex,
        sequence_id=sequence_id,
        document=None,
        deleted=False,
    )
