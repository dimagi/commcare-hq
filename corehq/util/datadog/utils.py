from __future__ import absolute_import
import re
import logging
from functools import wraps

from corehq.util.datadog import statsd, COMMON_TAGS, datadog_logger
from datadog import api

from corehq.util.datadog.const import ALERT_INFO

WILDCARD = '*'
DATADOG_WEB_USERS_GAUGE = 'commcare.hubspot.web_users_processed'
DATADOG_DOMAINS_EXCEEDING_FORMS_GAUGE = 'commcare.hubspot.domains_with_forms_gt_threshold'
DATADOG_HUBSPOT_SENT_FORM_METRIC = 'commcare.hubspot.sent_form'
DATADOG_HUBSPOT_TRACK_DATA_POST_METRIC = 'commcare.hubspot.track_data_post'


def count_by_response_code(metric_name):
    from corehq.util.datadog.gauges import datadog_counter

    def _wrapper(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            response = fn(*args, **kwargs)

            try:
                datadog_counter(metric_name, tags=[
                    'status_code:{}'.format(response.status_code)
                ])
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
        except Exception as e:
            datadog_logger.exception('Error creating Datadog event', e)
    else:
        datadog_logger.debug('Datadog event: (%s) %s\n%s', alert_type, title, text)


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


def get_url_group(url):
    default = 'other'
    if url.startswith('/a/' + WILDCARD):
        parts = url.split('/')
        return parts[3] if len(parts) >= 4 else default

    return default


def update_datadog_metrics(metrics):
    for metric, value in metrics.items():
        statsd.gauge(metric, value)


def bucket_value(value, buckets, unit=''):
    """Get value bucket for the given value

    Bucket values because datadog's histogram is too limited

    Basically frequency is not high enough to have a meaningful
    distribution with datadog's 10s aggregation window, especially
    with tags. More details:
    https://help.datadoghq.com/hc/en-us/articles/211545826
    """
    for bucket in buckets:
        if value < bucket:
            return "lt_{:03}{}".format(bucket, unit)
    return "over_{:03}{}".format(buckets[-1], unit)
