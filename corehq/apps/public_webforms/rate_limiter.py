from django.conf import settings

from corehq.project_limits.rate_limiter import (
    RateDefinition,
    RateLimiter,
    get_dynamic_rate_definition,
)
from dimagi.utils.web import get_ip

from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.global_request import get_request
from corehq.util.metrics import metrics_counter

STATUS_GLOBAL_RATE_LIMITED = 'global_rate_limited'
STATUS_IP_RATE_LIMITED = 'ip_rate_limited'
STATUS_CONTACT_RATE_LIMITED = 'contact_rate_limited'
STATUS_ACCEPTED = 'accepted'

SHOULD_RATE_LIMIT_LINK_REQUESTS = not settings.UNIT_TESTING


@run_only_when(lambda: SHOULD_RATE_LIMIT_LINK_REQUESTS)
@silence_and_report_error(
    "Exception raised in the public webform link request rate limiter",
    'commcare.public_webforms.link_request_rate_limiter_errors')
def rate_limit_link_request(contact):
    ip_address = _get_ip_address()
    status, window = _check_for_exceeded_rate_limits(contact, ip_address)
    if status == STATUS_ACCEPTED:
        _report_usage(contact, ip_address)

    metrics_counter('commcare.public_webforms.link_requests', 1, tags={
        'status': status,
        'window': window or 'none',
    })
    return status != STATUS_ACCEPTED


def _get_ip_address():
    request = get_request()
    return get_ip(request) if request else None


def _check_for_exceeded_rate_limits(contact, ip_address):
    # widest scope first, so that the metric names the broadest limit reached
    window = link_requests_global.get_window_of_first_exceeded_limit()
    if window:
        return STATUS_GLOBAL_RATE_LIMITED, window

    if ip_address:
        window = link_requests_per_ip.get_window_of_first_exceeded_limit(
            'ip:{}'.format(ip_address))
        if window:
            return STATUS_IP_RATE_LIMITED, window

    window = link_requests_per_contact.get_window_of_first_exceeded_limit(
        'contact:{}'.format(contact))
    if window:
        return STATUS_CONTACT_RATE_LIMITED, window

    return STATUS_ACCEPTED, None


def _report_usage(contact, ip_address):
    link_requests_global.report_usage()
    if ip_address:
        link_requests_per_ip.report_usage('ip:{}'.format(ip_address))
    link_requests_per_contact.report_usage('contact:{}'.format(contact))


link_requests_per_contact = RateLimiter(
    feature_key='public_webform_link_requests_per_contact',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_link_requests_per_contact',
        default=RateDefinition(
            per_week=30,
            per_day=15,
            per_hour=5,
        )
    ).get_rate_limits(scope),
)


link_requests_per_ip = RateLimiter(
    feature_key='public_webform_link_requests_per_ip',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_link_requests_per_ip',
        # generous, because a clinic full of respondents may share one address
        default=RateDefinition(
            per_week=2000,
            per_day=500,
            per_hour=100,
        )
    ).get_rate_limits(scope),
)

link_requests_global = RateLimiter(
    feature_key='public_webform_link_requests_global',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_link_requests_global',
        # a ceiling on what the feature can cost HQ, not a per-project limit
        default=RateDefinition(
            per_day=50000,
            per_hour=5000,
        )
    ).get_rate_limits(scope),
)
