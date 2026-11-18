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
STATUS_DOMAIN_RATE_LIMITED = 'domain_rate_limited'
STATUS_IP_RATE_LIMITED = 'ip_rate_limited'
STATUS_CONTACT_RATE_LIMITED = 'contact_rate_limited'
STATUS_SESSION_RATE_LIMITED = 'session_rate_limited'
STATUS_ACCEPTED = 'accepted'

SHOULD_RATE_LIMIT_ACCESS_REQUESTS = not settings.UNIT_TESTING


@run_only_when(lambda: SHOULD_RATE_LIMIT_ACCESS_REQUESTS)
@silence_and_report_error(
    "Exception raised in the public webform access request rate limiter",
    'commcare.public_webforms.access_request_rate_limiter_errors')
def rate_limit_access_request(domain, contact):
    ip_address = _get_ip_address()
    status, window = _check_for_exceeded_rate_limits(
        domain, contact, ip_address
    )
    if status == STATUS_ACCEPTED:
        _report_usage(domain, contact, ip_address)
    soft_status = _check_and_report_soft_usage(domain, ip_address) or 'unknown'

    metrics_counter('commcare.public_webforms.access_requests', 1, tags={
        'status': status,
        'window': window or 'none',
        'soft_status': soft_status,
    })
    return status != STATUS_ACCEPTED


def _get_ip_address():
    request = get_request()
    return get_ip(request) if request else None


def _check_for_exceeded_rate_limits(domain, contact, ip_address):
    # widest scope first, so that the metric names the broadest limit reached
    window = access_requests_global.get_window_of_first_exceeded_limit()
    if window:
        return STATUS_GLOBAL_RATE_LIMITED, window

    window = access_requests_per_domain.get_window_of_first_exceeded_limit(
        'domain:{}'.format(domain))
    if window:
        return STATUS_DOMAIN_RATE_LIMITED, window

    if ip_address:
        window = access_requests_per_ip.get_window_of_first_exceeded_limit(
            'ip:{}'.format(ip_address))
        if window:
            return STATUS_IP_RATE_LIMITED, window

    window = access_requests_per_contact.get_window_of_first_exceeded_limit(
        'contact:{}'.format(contact))
    if window:
        return STATUS_CONTACT_RATE_LIMITED, window

    return STATUS_ACCEPTED, None


def _report_usage(domain, contact, ip_address):
    access_requests_global.report_usage()
    access_requests_per_domain.report_usage('domain:{}'.format(domain))
    if ip_address:
        access_requests_per_ip.report_usage('ip:{}'.format(ip_address))
    access_requests_per_contact.report_usage('contact:{}'.format(contact))


@silence_and_report_error(
    "Exception raised in the public webform access request soft rate limiter",
    'commcare.public_webforms.access_request_soft_rate_limiter_errors')
def _check_and_report_soft_usage(domain, ip_address):
    status = _check_for_exceeded_soft_rate_limits(domain, ip_address)
    soft_access_requests_global.report_usage()
    soft_access_requests_per_domain.report_usage('domain:{}'.format(domain))
    if ip_address:
        soft_access_requests_per_ip.report_usage('ip:{}'.format(ip_address))
    return status


def _check_for_exceeded_soft_rate_limits(domain, ip_address):
    if soft_access_requests_global.get_window_of_first_exceeded_limit():
        return STATUS_GLOBAL_RATE_LIMITED
    if soft_access_requests_per_domain.get_window_of_first_exceeded_limit(
            'domain:{}'.format(domain)):
        return STATUS_DOMAIN_RATE_LIMITED
    if ip_address and soft_access_requests_per_ip.get_window_of_first_exceeded_limit(
            'ip:{}'.format(ip_address)):
        return STATUS_IP_RATE_LIMITED
    return STATUS_ACCEPTED


@silence_and_report_error(
    "Exception raised in the public webform session request rate limiter",
    'commcare.public_webforms.session_request_rate_limiter_errors')
def rate_limit_session_request(session_id):
    scope = 'session:{}'.format(session_id)
    window = requests_per_session.get_window_of_first_exceeded_limit(scope)
    if window is None:
        requests_per_session.report_usage(scope)

    metrics_counter('commcare.public_webforms.session_requests', 1, tags={
        'status': STATUS_SESSION_RATE_LIMITED if window else STATUS_ACCEPTED,
        'window': window or 'none',
    })
    return window is not None


access_requests_per_contact = RateLimiter(
    feature_key='public_webform_access_requests_per_contact',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_access_requests_per_contact',
        default=RateDefinition(
            per_week=30,
            per_day=15,
            per_hour=5,
        )
    ).get_rate_limits(scope),
)


access_requests_per_ip = RateLimiter(
    feature_key='public_webform_access_requests_per_ip',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_access_requests_per_ip',
        # generous, because a clinic full of respondents may share one address
        default=RateDefinition(
            per_week=2000,
            per_day=500,
            per_hour=100,
        )
    ).get_rate_limits(scope),
)

access_requests_per_domain = RateLimiter(
    feature_key='public_webform_access_requests_per_domain',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_access_requests_per_domain',
        default=RateDefinition(
            per_week=60000,
            per_day=20000,
            per_hour=3000,
        )
    ).get_rate_limits(scope),
)

access_requests_global = RateLimiter(
    feature_key='public_webform_access_requests_global',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_access_requests_global',
        # a ceiling on what the feature can cost HQ as a whole
        default=RateDefinition(
            per_day=500000,
            per_hour=50000,
        )
    ).get_rate_limits(scope),
)

soft_access_requests_per_ip = RateLimiter(
    feature_key='public_webform_soft_access_requests_per_ip',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_soft_access_requests_per_ip',
        default=RateDefinition(per_hour=10),
    ).get_rate_limits(scope),
)

soft_access_requests_per_domain = RateLimiter(
    feature_key='public_webform_soft_access_requests_per_domain',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_soft_access_requests_per_domain',
        default=RateDefinition(per_hour=300),
    ).get_rate_limits(scope),
)

soft_access_requests_global = RateLimiter(
    feature_key='public_webform_soft_access_requests_global',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_soft_access_requests_global',
        default=RateDefinition(per_hour=5000),
    ).get_rate_limits(scope),
)

requests_per_session = RateLimiter(
    feature_key='public_webform_requests_per_session',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'public_webform_requests_per_session',
        default=RateDefinition(per_minute=90, per_second=10),
    ).get_rate_limits(scope),
)
