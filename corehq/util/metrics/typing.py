from typing import Literal, Union

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
Tags = dict[str, str]
