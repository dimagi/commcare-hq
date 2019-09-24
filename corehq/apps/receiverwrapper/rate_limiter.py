from corehq.project_limits.rate_limiter import RateDefinition, RateLimiter, \
    PerUserRateDefinition

from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.utils import bucket_value
from corehq.util.decorators import silence_and_report_error, enterprise_skip
from corehq.util.timer import TimingContext


# Danny promised in an Aug 2019 email not to enforce limits that were lower than this.
# If we as a team end up regretting this decision, we'll have to reset expectations
# with the Dimagi NDoH team.
rates_promised_not_to_go_lower_than = RateDefinition(
    per_week=115,
    per_day=23,
    per_hour=3,
    per_minute=0.07,
    per_second=0.005,
)

floor_for_small_domain = RateDefinition(
    per_week=100,
    per_day=50,
    per_hour=30,
    per_minute=10,
    per_second=1,
)

test_rates = PerUserRateDefinition(
    per_user_rate_definition=rates_promised_not_to_go_lower_than.times(2.0),
    constant_rate_definition=floor_for_small_domain,
)

submission_rate_limiter = RateLimiter(
    feature_key='submissions',
    get_rate_limits=test_rates.get_rate_limits
)


@enterprise_skip
@silence_and_report_error("Exception raised in the submission rate limiter",
                          'commcare.xform_submissions.rate_limiter_errors')
def rate_limit_submission_by_delaying(domain, max_wait):
    if not submission_rate_limiter.allow_usage(domain):
        with TimingContext() as timer:
            acquired = submission_rate_limiter.wait(domain, timeout=max_wait)
        if acquired:
            duration_tag = bucket_value(timer.duration, [1, 5, 10, 15, 20], unit='s')
        else:
            duration_tag = 'timeout'
        datadog_counter('commcare.xform_submissions.rate_limited.test', tags=[
            'domain:{}'.format(domain),
            'duration:{}'.format(duration_tag)
        ])
    submission_rate_limiter.report_usage(domain)
