from collections import defaultdict
from contextlib import contextmanager

import mock

from corehq.util.metrics import DebugMetrics


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


@contextmanager
def capture_metrics():
    from corehq.util.metrics import _metrics
    capture = DebugMetrics(capture=True)
    _metrics.append(capture)
    try:
        yield capture.metrics
    finally:
        assert _metrics[-1] is capture, _metrics
        _metrics.pop()
