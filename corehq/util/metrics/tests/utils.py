from collections import defaultdict
from contextlib import contextmanager

import mock


@contextmanager
def patch_datadog():
    def record(fn, name, value, tags=None):
        def get_tag_pairs(tags: list):
            return tuple(sorted(tuple(t.split(':', 1)) for t in tags))
        key = (name, get_tag_pairs(tags or []))
        stats[key].append(value)

    stats = defaultdict(list)
    with mock.patch("corehq.util.metrics.datadog._datadog_record", new=record):
        yield stats
