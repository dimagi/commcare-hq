from typing import Any, Literal, Protocol, Union

AlertStr = Literal[
    'error',
    'warning',
    'info',
    'success',
]

# See PrometheusMetrics._gauge for documentation. This is only passed to
# PrometheusMetrics since it is one of PrometheusMetrics.accepted_gauge_params
PrometheusMultiprocessModeStr = Literal[
    'all',
    'liveall',
    'livesum',
    'max',
    'min',
]

Bucket = Union[float, int]
BucketName = str
MetricValue = Union[float, int]
TagValues = dict[str, str]


class LockProto(Protocol):
    name: str

    def acquire(self, *args: Any, **kwarg: Any) -> bool:
        ...

    def release(self) -> None:
        ...
