import logging

from django.conf import settings

from corehq.util.datadog.utils import bucket_value
from corehq.util.metrics.metrics import (
    HqCounter,
    HqGauge,
    HqHistogram,
    HqMetrics,
)
from datadog import api
from datadog.dogstatsd.base import DogStatsd

datadog_logger = logging.getLogger('datadog')

COMMON_TAGS = ['environment:{}'.format(settings.SERVER_ENVIRONMENT)]

statsd = DogStatsd(constant_tags=COMMON_TAGS)


def _format_tags(tag_values: dict):
    if not tag_values:
        return None

    return [
        f'{name}:{value}' for name, value in tag_values.items()
    ]


def _datadog_record(fn, name, value, tags=None):
    try:
        fn(name, value, tags=tags)
    except Exception:
        datadog_logger.exception('Unable to record Datadog stats')


class Counter(HqCounter):
    def _record(self, amount: float):
        tags = _format_tags(self.tag_values)
        _datadog_record(statsd.increment, self.name, amount, tags)


class Gauge(HqGauge):
    def _record(self, value):
        tags = _format_tags(self.tag_values)
        _datadog_record(statsd.gauge, self.name, value, tags)


class Histogram(HqHistogram):
    """This implementation of histogram uses tagging to record the buckets.
    It does not use the Datadog Histogram metric type.

    The metric itself will be incremented by 1 on each call to `observe`. The value
    passed to `observe` will be used to create the bucket tag.

    For example:

        h = Histogram(
            'commcare.request.duration', 'description',
            bucket_tag='duration', buckets=[1,2,3], bucket_units='ms'
        )
        h.observe(1.4)

        # resulting Datadog metric
        #    commcare.request.duration:1|c|#duration:lt_2ms

    For more details see:
    * https://github.com/dimagi/commcare-hq/pull/17080
    * https://github.com/dimagi/commcare-hq/pull/17030#issuecomment-315794700
    """
    def _record(self, value: float):
        tags = _format_tags(self.tag_values)
        if not tags:
            tags = []
        bucket = bucket_value(value, self._buckets, self._bucket_unit)
        tags.append(f'{self._bucket_tag}:{bucket}')
        _datadog_record(statsd.increment, self.name, 1, tags)


class DatadogMetrics(HqMetrics):
    _counter_class = Counter
    _gauge_class = Gauge
    _histogram_class = Histogram

    def enabled(self) -> bool:
        return api._api_key and api._application_key
