from django.conf import settings

from dimagi.utils.web import get_ip

from corehq.project_limits.rate_limiter import (
    RateDefinition,
    RateLimiter,
    get_dynamic_rate_definition,
)
from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.global_request import get_request
from corehq.util.metrics import metrics_counter

STATUS_SESSION_RATE_LIMITED = 'session_rate_limited'
STATUS_IP_RATE_LIMITED = 'ip_rate_limited'
STATUS_BAD_REQUEST = 'bad_request'
STATUS_ACCEPTED = 'accepted'


@run_only_when(not settings.UNIT_TESTING)
@silence_and_report_error("Exception raised in the check username availability rate limiter",
                          'commcare.registration.check_username_rate_limiter_errors')
def rate_limit_check_username_availability():
    """
    This holds attempts per IP OR per session below limits given by
    check_username_rate_limiter_by_ip and check_username_rate_limiter_by_session, respectively.

    Requests without both an IP and session ID are rejected.
    """
    session_id, ip_address = _get_session_and_ip()

    if ip_address and session_id:
        status, window = _check_for_exceeded_rate_limits(session_id, ip_address)
        if status == STATUS_ACCEPTED:
            check_username_rate_limiter_per_session.report_usage('session:{}'.format(session_id))
            check_username_rate_limiter_per_ip.report_usage('ip:{}'.format(ip_address))
    else:
        window = None
        status = STATUS_BAD_REQUEST

    metrics_counter('commcare.registration.check_username_attempts', 1, tags={
        'status': status,
        'window': window or 'none',
    })
    return status != STATUS_ACCEPTED


def _get_session_and_ip():
    request = get_request()
    if request and request.session:
        session_id = request.session.session_key
        ip_address = get_ip(request)
    else:
        session_id, ip_address = None, None

    return session_id, ip_address


def _check_for_exceeded_rate_limits(session, ip):
    session_window = (
        check_username_rate_limiter_per_session
        .get_window_of_first_exceeded_limit('session:{}'.format(session))
    )
    ip_window = check_username_rate_limiter_per_ip.get_window_of_first_exceeded_limit('ip:{}'.format(ip))

    # ensure that no rate limit windows have been exceeded
    # order of priority (session, ip)
    if session_window is not None:
        return STATUS_SESSION_RATE_LIMITED, session_window
    elif ip_window is not None:
        return STATUS_IP_RATE_LIMITED, ip_window
    else:
        return STATUS_ACCEPTED, None


check_username_rate_limiter_per_ip = RateLimiter(
    feature_key='check_username_attempts_per_ip',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'check_username_attempts_per_ip',
        default=RateDefinition(
            per_week=5000,
            per_day=2500,
            per_hour=1000,
            per_minute=200,
            per_second=25,
        )
    ).get_rate_limits(scope),
)

check_username_rate_limiter_per_session = RateLimiter(
    feature_key='check_username_attempts_per_session',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'check_username_attempts_per_session',
        default=RateDefinition(
            per_week=500,
            per_day=250,
            per_hour=100,
            per_minute=20,
            per_second=2.5,
        )
    ).get_rate_limits(scope),
)
