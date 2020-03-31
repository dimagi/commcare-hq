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


class CapturedMetrics:
    def __init__(self, samples):
        self._samples = samples

    def list(self, name: str, **tags):
        return [
            sample for sample in self._samples
            if sample.name == name and (not tags or sample.match_tags(tags))
        ]

    def sum(self, name: str, **tags):
        return sum([sample.value for sample in self.list(name, **tags)])


@contextmanager
def capture_metrics():
    from corehq.util.metrics import _metrics
    capture = DebugMetrics(capture=True)
    _metrics.append(capture)
    try:
        yield CapturedMetrics(capture.metrics)
    finally:
        assert _metrics[-1] is capture, _metrics
        _metrics.pop()
