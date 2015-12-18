import re
import logging
from functools import wraps

from datadog.api.exceptions import DatadogException

from corehq.util.datadog import statsd, COMMON_TAGS, datadog_logger
from datadog import api


from corehq.util.datadog.const import ALERT_INFO

datadog_metric_logger = logging.getLogger('datadog-metrics')

WILDCARD = '*'


def count_by_response_code(metric_prefix):
    def _wrapper(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            response = fn(*args, **kwargs)

            try:
                metric_name = '{}.{}'.format(metric_prefix, response.status_code)
                statsd.increment(metric_name)
            except Exception:
                datadog_logger.exception('Unable to record Datadog stats')

            return response

        return _inner
    return _wrapper


def datadog_initialized():
    return api._api_key and api._application_key


def create_datadog_event(title, text, alert_type=ALERT_INFO, tags=None, aggregation_key=None):
    tags = COMMON_TAGS + (tags or [])
    if datadog_initialized():
        try:
            api.Event.create(
                title=title, text=text, tags=tags,
                alert_type=alert_type, aggregation_key=aggregation_key,
            )
        except DatadogException:
            datadog_logger.exception('Error creating Datadog event')
    else:
        datadog_logger.debug('Datadog event: (%s) %s\n%s', alert_type, title, text)


def log_counter(metric, details=None):
    details = details or {}
    message = ' '.join(['{}={}'.format(key, value) for key, value in details.iteritems()])
    datadog_metric_logger.info(
        message,
        extra={
            'value': 1,
            'metric_type': 'counter',
            'metric': metric,
        },
    )


def sanitize_url(url):
    # Normalize all domain names
    url = re.sub(r'/a/[0-9a-z-]+', '/a/{}'.format(WILDCARD), url)

    # Normalize all urls with indexes or ids
    url = re.sub(r'/modules-[0-9]+', '/modules-{}'.format(WILDCARD), url)
    url = re.sub(r'/forms-[0-9]+', '/forms-{}'.format(WILDCARD), url)
    url = re.sub(r'/form_data/[a-z0-9-]+', '/form_data/{}'.format(WILDCARD), url)
    url = re.sub(r'/uuid:[a-z0-9-]+', '/uuid:{}'.format(WILDCARD), url)
    url = re.sub(r'[-0-9a-f]{10,}', '{}'.format(WILDCARD), url)

    # Remove URL params
    url = re.sub(r'\?[^ ]*', '', url)
    return url
