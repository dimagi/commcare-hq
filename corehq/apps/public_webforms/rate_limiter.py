from django.conf import settings

from corehq.project_limits.rate_limiter import (
    RateDefinition,
    RateLimiter,
    get_dynamic_rate_definition,
)
from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.metrics import metrics_counter

STATUS_CONTACT_RATE_LIMITED = 'contact_rate_limited'
STATUS_ACCEPTED = 'accepted'

SHOULD_RATE_LIMIT_LINK_REQUESTS = not settings.UNIT_TESTING


@run_only_when(lambda: SHOULD_RATE_LIMIT_LINK_REQUESTS)
@silence_and_report_error(
    "Exception raised in the public webform link request rate limiter",
    'commcare.public_webforms.link_request_rate_limiter_errors')
def rate_limit_link_request(contact):
    scope = 'contact:{}'.format(contact)
    window = link_requests_per_contact.get_window_of_first_exceeded_limit(scope)
    status = STATUS_CONTACT_RATE_LIMITED if window else STATUS_ACCEPTED
    if status == STATUS_ACCEPTED:
        link_requests_per_contact.report_usage(scope)

    metrics_counter('commcare.public_webforms.link_requests', 1, tags={
        'status': status,
        'window': window or 'none',
    })
    return status != STATUS_ACCEPTED


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
