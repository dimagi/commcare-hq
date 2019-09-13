from django.conf import settings

from corehq.project_limits.rate_limiter import RateDefinition, RateLimiter, \
    PerUserRateDefinition

# Danny promised in an Aug 2019 email not to enforce limits that were lower than this.
# If we as a team end up regretting this decision, we'll have to reset expectations
# with the Dimagi NDoH team.
from corehq.util.datadog.gauges import datadog_counter
from dimagi.utils.logging import notify_exception

rates_promised_not_to_go_lower_than = RateDefinition(
    per_week=115,
    per_day=23,
    per_hour=3,
    per_minute=0.07,
    per_second=0.005,
)

floor_for_small_domain = RateDefinition(
    per_day=50,
    per_hour=30,
    per_minute=10,
    per_second=1,
)

test_rates = PerUserRateDefinition(
    per_user_rate_definition=rates_promised_not_to_go_lower_than.times(2.0),
    min_rate_definition=floor_for_small_domain,
)

submission_rate_limiter = RateLimiter(
    feature_key='submissions',
    get_rate_limits=test_rates.get_rate_limits
)


def rate_limit_submission_noop(domain):
    if not settings.ENTERPRISE_MODE:
        try:
            if not submission_rate_limiter.allow_usage(domain):
                datadog_counter('commcare.xform_submissions.rate_limited.test', tags=[
                    'domain:{}'.format(domain),
                ])
            submission_rate_limiter.report_usage(domain)
        except Exception:
            # Prevent rate limiting logic from ever blocking as submission if it errors
            # until it is proven to be a stable and essential part of our system.
            # Instead, report the issue to sentry and track the overall count on datadog
            notify_exception(request, "Exception raised in the rate limiter")
            datadog_counter('commcare.xform_submissions.rate_limiter_errors', tags=[
                'domain:{}'.format(domain),
            ])
            if settings.UNIT_TESTING:
                raise
