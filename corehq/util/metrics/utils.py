from datetime import timedelta

from django.conf import settings


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
    if (settings.SERVER_ENVIRONMENT, domain_name) in settings.METRICS_TAGGED_DOMAINS:
        tags['domain'] = domain_name
