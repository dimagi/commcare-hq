import logging
from typing import List

from django.conf import settings

from corehq.util.datadog.utils import bucket_value
from corehq.util.metrics.metrics import HqMetrics
from datadog import api
from datadog.dogstatsd.base import DogStatsd

datadog_logger = logging.getLogger('datadog')

COMMON_TAGS = ['environment:{}'.format(settings.SERVER_ENVIRONMENT)]

statsd = DogStatsd(constant_tags=COMMON_TAGS)


class DatadogMetrics(HqMetrics):
    def validate(self):
        if not (api._api_key and api._application_key):
            raise Exception("Datadog not configured. Set DATADOG_API_KEY and DATADOG_APP_KEY in settings.")

    def _counter(self, name: str, value: float, tags: dict = None, documentation: str = ''):
        dd_tags = _format_tags(tags)
        _datadog_record(statsd.increment, name, value, dd_tags)

    def _gauge(self, name: str, value: float, tags: dict = None, documentation: str = ''):
        dd_tags = _format_tags(tags)
        _datadog_record(statsd.gauge, name, value, dd_tags)

    def _histogram(self, name: str, value: float,
                  bucket_tag: str, buckets: List[int], bucket_unit: str = '',
                  tags: dict = None, documentation: str = ''):
        """
        This implementation of histogram uses tagging to record the buckets.
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
        tags = _format_tags(tags)
        if not tags:
            tags = []
        bucket = bucket_value(value, buckets, bucket_unit)
        tags.append(f'{bucket_tag}:{bucket}')
        _datadog_record(statsd.increment, name, 1, tags)


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
