import re
from datetime import timedelta

WILDCARD = '*'


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
