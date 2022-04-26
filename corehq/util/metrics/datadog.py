import logging
from collections.abc import Sequence
from typing import Any, Callable, Optional, Union, overload

from django.conf import settings

from datadog.api import (  # type: ignore[attr-defined]
    Event,
    _api_key,
    _application_key,
)
from datadog.dogstatsd.base import DogStatsd

from corehq.util.metrics.const import ALERT_INFO, COMMON_TAGS
from corehq.util.metrics.metrics import HqMetrics
from corehq.util.metrics.typing import AlertStr, Bucket, MetricValue, TagValues
from corehq.util.metrics.utils import bucket_value

datadog_logger = logging.getLogger('datadog')

TagList = list[str]


@overload
def _format_tags(tag_values: TagValues) -> TagList:
    ...


@overload
def _format_tags(tag_values: None) -> None:
    ...


def _format_tags(tag_values: Optional[TagValues]) -> Optional[TagList]:
    if not tag_values:
        return None
    return [f'{name}:{value}' for name, value in tag_values.items()]


statsd = DogStatsd(constant_tags=_format_tags(COMMON_TAGS))


class DatadogMetrics(HqMetrics):
    """Datadog Metrics Provider

    Settings:
    * DATADOG_API_KEY
    * DATADOG_APP_KEY
    """

    def __init__(self) -> None:
        if settings.UNIT_TESTING:
            return

        if not settings.DATADOG_API_KEY or not settings.DATADOG_APP_KEY:
            raise Exception(
                "Datadog not configured. "
                "Set DATADOG_API_KEY and DATADOG_APP_KEY in settings or update METRICS_PROVIDERS "
                "to remove the Datadog provider."
            )

        try:
            from datadog import initialize
        except ImportError:
            pass
        else:
            initialize(settings.DATADOG_API_KEY, settings.DATADOG_APP_KEY)

    def _counter(
        self,
        name: str,
        value: MetricValue,
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        """Although this is submitted as a COUNT the Datadog app represents these as a RATE.
        See https://docs.datadoghq.com/developers/metrics/types/?tab=rate#definition"""
        dd_tags = _format_tags(tags)
        _datadog_record(statsd.increment, name, value, dd_tags)

    def _gauge(
        self,
        name: str,
        value: MetricValue,
        tags: Optional[TagValues] = None,
        documentation: str = '',
        **kwargs: Any,
    ) -> None:
        """See https://docs.datadoghq.com/developers/metrics/types/?tab=gauge#definition"""
        dd_tags = _format_tags(tags)
        _datadog_record(statsd.gauge, name, value, dd_tags)

    def _histogram(
        self,
        name: str,
        value: MetricValue,
        bucket_tag: str,
        buckets: Sequence[Bucket],
        bucket_unit: str = '',
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        """
        This implementation of histogram uses tagging to record the buckets.
        It does not use the Datadog Histogram metric type.

        The metric itself will be incremented by 1 on each call. The value
        passed to `metrics_histogram` will be used to create the bucket tag.

        For example:

        ::

            h = metrics_histogram(
                'commcare.request.duration', 1.4,
                bucket_tag='duration', buckets=[1, 2, 3], bucket_unit='ms',
                tags=tags
            )

            # resulting metrics
            # commcare.request.duration:1|c|#duration:lt_2ms

        For more explanation about why this implementation was chosen see:

        * https://github.com/dimagi/commcare-hq/pull/17080
        * https://github.com/dimagi/commcare-hq/pull/17030#issuecomment-315794700
        """
        tag_list = _format_tags(tags) or []
        bucket = bucket_value(value, buckets, bucket_unit)
        tag_list.append(f'{bucket_tag}:{bucket}')
        _datadog_record(statsd.increment, name, 1, tag_list)

    def _create_event(
        self,
        title: str,
        text: str,
        alert_type: AlertStr = ALERT_INFO,
        tags: Optional[TagValues] = None,
        aggregation_key: Optional[str] = None,
    ) -> None:
        if datadog_initialized():
            Event.create(
                title=title,
                text=text,
                tags=tags,
                alert_type=alert_type,
                aggregation_key=aggregation_key,
            )
        else:
            datadog_logger.debug('Metrics event: (%s) %s\n%s\n%s', alert_type, title, text, tags)


def _datadog_record(
    fn: Callable[..., None],
    name: str,
    value: MetricValue,
    tags: Optional[TagList] = None,
) -> None:
    try:
        fn(name, value, tags=tags)
    except Exception:
        datadog_logger.exception('Unable to record Datadog stats')


def datadog_initialized() -> bool:
    return bool(_api_key and _application_key)
