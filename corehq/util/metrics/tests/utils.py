from collections import defaultdict
from contextlib import contextmanager

import mock

from corehq.util.metrics import DebugMetrics, DelegatedMetrics


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

    def to_flattened_dict(self):
        return {
            f'{sample.name}.{tag}:{value}': sample.value
            for sample in self._samples
            for tag, value in sample.tags.items()
        }

    def __contains__(self, metric_name: str):
        return any(sample.name == metric_name for sample in self._samples)

    def __repr__(self):
        return repr(self._samples)


@contextmanager
def capture_metrics():
    from corehq.util.metrics import _get_metrics_provider, _metrics  # noqa
    capture = DebugMetrics(capture=True)
    _get_metrics_provider()  # ensure _metrics is populated
    _metrics.append(DelegatedMetrics([capture] + _metrics))
    try:
        yield CapturedMetrics(capture.metrics)
    finally:
        assert _metrics[-1].delegates[0] is capture, _metrics
        _metrics.pop()
