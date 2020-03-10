import logging

from django.conf import settings

from corehq.util.metrics.metrics import HqCounter, HqGauge, HqMetrics
from datadog import api
from datadog.dogstatsd.base import DogStatsd

datadog_logger = logging.getLogger('datadog')

COMMON_TAGS = ['environment:{}'.format(settings.SERVER_ENVIRONMENT)]

statsd = DogStatsd(constant_tags=COMMON_TAGS)


def _format_tags(tag_names, tag_values):
    if not tag_names or not tag_values:
        return None

    return [
        f'{name}:{value}' for name, value in zip(tag_names, tag_values)
    ]


def _datadog_record(fn, name, value, tags=None):
    try:
        fn(name, value, tags=tags)
    except Exception:
        datadog_logger.exception('Unable to record Datadog stats')


class Counter(HqCounter):
    def _inc(self, amount=1):
        tags = _format_tags(self.tag_names, self.tag_values)
        _datadog_record(statsd.increment, self.name, amount, tags)


class Gauge(HqGauge):
    def _set(self, value):
        tags = _format_tags(self.tag_names, self.tag_values)
        _datadog_record(statsd.gauge, self.name, value, tags)


class DatadogMetrics(HqMetrics):
    _counter_class = Counter
    _gauge_class = Gauge

    def enabled(self) -> bool:
        return api._api_key and api._application_key
