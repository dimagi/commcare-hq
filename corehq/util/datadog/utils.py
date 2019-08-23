from __future__ import absolute_import
from __future__ import unicode_literals
import re
from datetime import timedelta
from functools import wraps, partial

from datadog import api
from django.conf import settings

from corehq.util.datadog import statsd, COMMON_TAGS, datadog_logger
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


def make_buckets_from_timedeltas(*timedeltas):
    return [td.total_seconds() for td in timedeltas]


DAY_SCALE_TIME_BUCKETS = make_buckets_from_timedeltas(
    timedelta(seconds=1),
    timedelta(seconds=10),
    timedelta(minutes=1),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=12),
    timedelta(hours=24),
)


def bucket_value(value, buckets, unit=''):
    """Get value bucket for the given value

    Bucket values because datadog's histogram is too limited

    Basically frequency is not high enough to have a meaningful
    distribution with datadog's 10s aggregation window, especially
    with tags. More details:
    https://help.datadoghq.com/hc/en-us/articles/211545826
    """
    buckets = sorted(buckets)
    number_length = max(len("{}".format(buckets[-1])), 3)
    lt_template = "lt_{:0%s}{}" % number_length
    over_template = "over_{:0%s}{}" % number_length
    for bucket in buckets:
        if value < bucket:
            return lt_template.format(bucket, unit)
    return over_template.format(buckets[-1], unit)


def maybe_add_domain_tag(domain_name, tags):
    """Conditionally add a domain tag to the given list of tags"""
    if (settings.SERVER_ENVIRONMENT, domain_name) in settings.DATADOG_DOMAINS:
        tags.append('domain:{}'.format(domain_name))


def load_counter(load_type, source, domain_name, extra_tags=None):
    """Make a function to track load by counting touched items

    :param load_type: Load type (`"case"`, `"form"`, `"sms"`). Use one
    of the convenience functions below (e.g., `case_load_counter`)
    rather than passing a string literal.
    :param source: Load source string. Example: `"form_submission"`.
    :param domain_name: Domain name string.
    :param extra_tags: Optional list of extra datadog tags.
    :returns: Function that adds load when called: `add_load(value=1)`.
    """
    from corehq.util.datadog.gauges import datadog_counter
    tags = ["src:%s" % source]
    if extra_tags:
        tags.extend(extra_tags)
    maybe_add_domain_tag(domain_name, tags)
    metric = "commcare.load.%s" % load_type

    def track_load(value=1):
        datadog_counter(metric, value, tags=tags)

    return track_load


def case_load_counter(*args, **kw):
    # grep: commcare.load.case
    return load_counter("case", *args, **kw)


def form_load_counter(*args, **kw):
    # grep: commcare.load.form
    return load_counter("form", *args, **kw)


def ledger_load_counter(*args, **kw):
    """Make a ledger transaction load counter function

    Each item counted is a ledger transaction (not a ledger value).
    """
    # grep: commcare.load.ledger
    return load_counter("ledger", *args, **kw)


def sms_load_counter(*args, **kw):
    """Make a messaging load counter function

    This is used to count all kinds of messaging load, including email
    (not strictly SMS).
    """
    # grep: commcare.load.sms
    return load_counter("sms", *args, **kw)


def ucr_load_counter(engine_id, *args, **kw):
    """Make a UCR load counter function

    This is used to count all kinds of UCR load
    """
    # grep: commcare.load.ucr
    return load_counter("ucr.{}".format(engine_id), *args, **kw)


def schedule_load_counter(*args, **kw):
    """Make a schedule load counter function

    This is used to count load from ScheduleInstances
    """
    # grep: commcare.load.schedule
    return load_counter("schedule", *args, **kw)


def load_counter_for_model(model):
    from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        AlertScheduleInstance, TimedScheduleInstance, CaseTimedScheduleInstance, CaseAlertScheduleInstance
    )
    return {
        CommCareCaseSQL: case_load_counter,
        XFormInstanceSQL: form_load_counter,
        AlertScheduleInstance: schedule_load_counter,
        TimedScheduleInstance: schedule_load_counter,
        CaseTimedScheduleInstance: schedule_load_counter,
        CaseAlertScheduleInstance: schedule_load_counter,
    }.get(model, partial(load_counter, 'unknown'))  # grep: commcare.load.unknown
