from django.conf import settings

from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
    RateLimiter,
    get_dynamic_rate_definition,
)
from corehq.project_limits.shortcuts import get_standard_ratio_rate_definition
from corehq.toggles import DO_NOT_RATE_LIMIT_SUBMISSIONS, \
    TEST_FORM_SUBMISSION_RATE_LIMIT_RESPONSE
from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.metrics import metrics_counter, metrics_gauge, bucket_value
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext

# Danny promised in an Aug 2019 email not to enforce limits that were lower than this.
#   RateDefinition(
#       per_week=115,
#       per_day=23,
#       per_hour=3,
#       per_minute=0.07,
#       per_second=0.005,
#   ) == get_standard_ratio_rate_definition(events_per_day=23)
# If we as a team end up regretting this decision, we'll have to reset expectations
# with the Dimagi NDoH team.


submission_rate_limiter = RateLimiter(
    feature_key='submissions',
    get_rate_limits=lambda domain: _get_per_user_submission_rate_definition(domain)
)


def _get_per_user_submission_rate_definition(domain):
    return PerUserRateDefinition(
        per_user_rate_definition=get_dynamic_rate_definition(
            'submissions_per_user',
            default=get_standard_ratio_rate_definition(events_per_day=46),
        ),
        constant_rate_definition=get_dynamic_rate_definition(
            'baseline_submissions_per_project',
            default=RateDefinition(
                per_week=100,
                per_day=50,
                per_hour=30,
                per_minute=10,
                per_second=1,
            ),
        ),
    ).get_rate_limits(domain)


global_submission_rate_limiter = RateLimiter(
    feature_key='global_submissions',
    get_rate_limits=lambda: get_dynamic_rate_definition(
        'global_submissions',
        default=RateDefinition(
            per_hour=17000,
            per_minute=400,
            per_second=30,
        )
    ).get_rate_limits(),
    scope_length=0,
)


SHOULD_RATE_LIMIT_SUBMISSIONS = settings.RATE_LIMIT_SUBMISSIONS and not settings.UNIT_TESTING


@run_only_when(SHOULD_RATE_LIMIT_SUBMISSIONS)
@silence_and_report_error("Exception raised in the submission rate limiter",
                          'commcare.xform_submissions.rate_limiter_errors')
def rate_limit_submission(domain):
    if TEST_FORM_SUBMISSION_RATE_LIMIT_RESPONSE.enabled(domain):
        return True
    should_allow_usage = (
        global_submission_rate_limiter.allow_usage()
        or submission_rate_limiter.allow_usage(domain))

    if should_allow_usage:
        allow_usage = True
    elif DO_NOT_RATE_LIMIT_SUBMISSIONS.enabled(domain):
        # If we're disabling rate limiting on a domain then allow it
        # but still delay and record whether they'd be rate limited under the 'test' metric
        allow_usage = True
        _delay_and_report_rate_limit_submission(
            domain, max_wait=15, datadog_metric='commcare.xform_submissions.rate_limited.test')
    else:
        allow_usage = _delay_and_report_rate_limit_submission(
            domain, max_wait=15, datadog_metric='commcare.xform_submissions.rate_limited')

    return not allow_usage


@run_only_when(SHOULD_RATE_LIMIT_SUBMISSIONS)
@silence_and_report_error("Exception raised reporting usage to the submission rate limiter",
                          'commcare.xform_submissions.report_usage_errors')
def report_submission_usage(domain):
    submission_rate_limiter.report_usage(domain)
    global_submission_rate_limiter.report_usage()
    _report_current_global_submission_thresholds()


def _delay_and_report_rate_limit_submission(domain, max_wait, datadog_metric):
    with TimingContext() as timer:
        acquired = submission_rate_limiter.wait(domain, timeout=max_wait)
    if acquired:
        duration_tag = bucket_value(timer.duration, [.5, 1, 5, 10, 15], unit='s')
    elif timer.duration < max_wait:
        duration_tag = 'quick_reject'
    else:
        duration_tag = 'delayed_reject'
    metrics_counter(datadog_metric, tags={
        'domain': domain,
        'duration': duration_tag,
        'throttle_method': "delay" if acquired else "reject"
    })
    return acquired


@quickcache([], timeout=60)  # Only report up to once a minute
def _report_current_global_submission_thresholds():
    for window, value, threshold in global_submission_rate_limiter.iter_rates():
        metrics_gauge('commcare.xform_submissions.global_threshold', threshold, tags={
            'window': window
        })
        metrics_gauge('commcare.xform_submissions.global_usage', value, tags={
            'window': window
        })
