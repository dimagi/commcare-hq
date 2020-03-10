from collections import defaultdict
from contextlib import contextmanager

import mock


@contextmanager
def patch_datadog():
    def record(fn, name, value, tags=None):
        key = tuple([
            name,
            tuple([tuple(t.split(':')) for t in (tags or [])]),
        ])
        stats[key].append(value)

    stats = defaultdict(list)
    patch = mock.patch("corehq.util.metrics.datadog._datadog_record", new=record)
    patch.start()
    try:
        yield stats
    finally:
        patch.stop()
