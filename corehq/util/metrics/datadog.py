import logging
from typing import List, Dict

from datadog import api
from django.conf import settings

from corehq.util.metrics.utils import bucket_value
from corehq.util.metrics.const import COMMON_TAGS, ALERT_INFO
from corehq.util.metrics.metrics import HqMetrics
from datadog.dogstatsd.base import DogStatsd

datadog_logger = logging.getLogger('datadog')


def _format_tags(tag_values: Dict[str, str]):
    if not tag_values:
        return None

    return [
        f'{name}:{value}' for name, value in tag_values.items()
    ]


statsd = DogStatsd(constant_tags=_format_tags(COMMON_TAGS))


class DatadogMetrics(HqMetrics):
    """Datadog Metrics Provider

    Settings:
    * DATADOG_API_KEY
    * DATADOG_APP_KEY
    """

    def __init__(self):
        if settings.UNIT_TESTING or settings.DEBUG or 'ddtrace.contrib.django' not in settings.INSTALLED_APPS:
            try:
                from ddtrace import tracer
                tracer.enabled = False
            except ImportError:
                pass

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

    def _counter(self, name: str, value: float, tags: Dict[str, str] = None, documentation: str = ''):
        """Although this is submitted as a COUNT the Datadog app represents these as a RATE.
        See https://docs.datadoghq.com/developers/metrics/types/?tab=rate#definition"""
        dd_tags = _format_tags(tags)
        _datadog_record(statsd.increment, name, value, dd_tags)

    def _gauge(self, name: str, value: float, tags: Dict[str, str] = None, documentation: str = ''):
        """See https://docs.datadoghq.com/developers/metrics/types/?tab=gauge#definition"""
        dd_tags = _format_tags(tags)
        _datadog_record(statsd.gauge, name, value, dd_tags)

    def _histogram(self, name: str, value: float,
                  bucket_tag: str, buckets: List[int], bucket_unit: str = '',
                  tags: Dict[str, str] = None, documentation: str = ''):
        """
        This implementation of histogram uses tagging to record the buckets.
        It does not use the Datadog Histogram metric type.

        The metric itself will be incremented by 1 on each call. The value
        passed to `metrics_histogram` will be used to create the bucket tag.

        For example:

        ::

            h = metrics_histogram(
                'commcare.request.duration', 1.4,
                bucket_tag='duration', buckets=[1,2,3], bucket_units='ms',
                tags=tags
            )

            # resulting metrics
            # commcare.request.duration:1|c|#duration:lt_2ms

        For more explanation about why this implementation was chosen see:

        * https://github.com/dimagi/commcare-hq/pull/17080
        * https://github.com/dimagi/commcare-hq/pull/17030#issuecomment-315794700
        """
        tags = _format_tags(tags)
        if not tags:
            tags = []
        bucket = bucket_value(value, buckets, bucket_unit)
        tags.append(f'{bucket_tag}:{bucket}')
        _datadog_record(statsd.increment, name, 1, tags)

    def _create_event(self, title: str, text: str, alert_type: str = ALERT_INFO,
                      tags: Dict[str, str] = None, aggregation_key: str = None):
        if datadog_initialized():
            api.Event.create(
                title=title, text=text, tags=tags,
                alert_type=alert_type, aggregation_key=aggregation_key,
            )
        else:
            datadog_logger.debug('Metrics event: (%s) %s\n%s\n%s', alert_type, title, text, tags)


def _datadog_record(fn, name, value, tags=None):
    try:
        fn(name, value, tags=tags)
    except Exception:
        datadog_logger.exception('Unable to record Datadog stats')


def datadog_initialized():
    return api._api_key and api._application_key
