from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Callable, Optional, Union, cast
from unittest import mock

from corehq.util.metrics import DebugMetrics, DelegatedMetrics
from corehq.util.metrics.datadog import TagList
from corehq.util.metrics.metrics import Sample, MetricsProto
from corehq.util.metrics.typing import MetricValue

TagPair = tuple[str, str]
TagPairs = tuple[TagPair, ...]
NamedTagPairs = tuple[str, TagPairs]
MetricValueList = list[MetricValue]
RecordedMetrics = dict[NamedTagPairs, MetricValueList]
TagPairsToValueMapping = dict[TagPairs, MetricValue]


@contextmanager
def patch_datadog() -> Generator[RecordedMetrics, None, None]:
    def record(
        fn: Callable[..., None],
        name: str,
        value: MetricValue,
        tags: Optional[TagList] = None
    ) -> None:

        def get_tag_pair(tag_str: str) -> TagPair:
            return cast(TagPair, tuple(tag_str.split(':', 1)))

        def get_tag_pairs(tag_list: TagList) -> TagPairs:
            return tuple(sorted(get_tag_pair(t) for t in tag_list))

        key: NamedTagPairs = (name, get_tag_pairs(tags or []))
        stats[key].append(value)

    stats: RecordedMetrics = defaultdict(list)
    with mock.patch("corehq.util.metrics.datadog._datadog_record", new=record):
        yield stats


class CapturedMetrics:
    def __init__(self, samples: list[Sample]) -> None:
        self._samples = samples

    def list(self, name: str, **tags: Any) -> list[Sample]:
        return [
            sample for sample in self._samples
            if sample.name == name and (not tags or sample.match_tags(tags))
        ]

    def sum(self, name: str, **tags: Any) -> Union[int, float]:
        return sum([sample.value for sample in self.list(name, **tags)])

    def to_flattened_dict(self) -> dict[str, Union[int, float]]:
        return {
            f'{sample.name}.{tag}:{value}': sample.value
            for sample in self._samples
            for tag, value in sample.tags.items()
        }

    def __contains__(self, metric_name: str) -> bool:
        return any(sample.name == metric_name for sample in self._samples)

    def __repr__(self) -> str:
        return repr(self._samples)


@contextmanager
def capture_metrics() -> Generator[CapturedMetrics, None, None]:
    from corehq.util.metrics import _get_metrics_provider, _metrics  # noqa
    capture = DebugMetrics(capture=True)
    capture_list: list[MetricsProto] = [capture]
    _get_metrics_provider()  # ensure _metrics is populated
    delegated_metrics = DelegatedMetrics(capture_list + _metrics)
    _metrics.append(delegated_metrics)
    try:
        yield CapturedMetrics(capture.metrics)
    finally:
        assert delegated_metrics.delegates[0] is capture, _metrics
        _metrics.pop()
