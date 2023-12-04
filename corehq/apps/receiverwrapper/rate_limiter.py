import time

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
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'global_submissions',
        default=RateDefinition(
            per_hour=17000,
            per_minute=400,
            per_second=30,
        )
    ).get_rate_limits(),
)


global_case_rate_limiter = RateLimiter(
    feature_key='global_case_updates',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'global_case_updates',
        default=RateDefinition(
            per_hour=170000,
            per_minute=4000,
            per_second=300,
        )
    ).get_rate_limits(),
)


def _get_per_user_case_rate_definition(domain):
    return PerUserRateDefinition(
        per_user_rate_definition=get_dynamic_rate_definition(
            'case_updates_per_user',
            default=get_standard_ratio_rate_definition(events_per_day=460),
        ),
        constant_rate_definition=get_dynamic_rate_definition(
            'baseline_case_updates_per_project',
            default=RateDefinition(
                per_week=1000,
                per_day=500,
                per_hour=300,
                per_minute=100,
                per_second=10,
            ),
        ),
    ).get_rate_limits(domain)


domain_case_rate_limiter = RateLimiter(
    feature_key='domain_case_updates',
    get_rate_limits=lambda domain: _get_per_user_case_rate_definition(domain)
)


SHOULD_RATE_LIMIT_SUBMISSIONS = settings.RATE_LIMIT_SUBMISSIONS and not settings.UNIT_TESTING


@run_only_when(lambda: SHOULD_RATE_LIMIT_SUBMISSIONS)
@silence_and_report_error("Exception raised in the submission rate limiter",
                          'commcare.xform_submissions.rate_limiter_errors')
def rate_limit_submission(domain, delay_rather_than_reject=False, max_wait=15):
    if TEST_FORM_SUBMISSION_RATE_LIMIT_RESPONSE.enabled(domain):
        return True
    allow_form_usage = (
        global_submission_rate_limiter.allow_usage()
        or submission_rate_limiter.allow_usage(domain))

    allow_case_usage = (
        global_case_rate_limiter.allow_usage()
        or domain_case_rate_limiter.allow_usage(domain))

    if allow_form_usage:
        allow_usage = True
    elif DO_NOT_RATE_LIMIT_SUBMISSIONS.enabled(domain):
        # If we're disabling rate limiting on a domain then allow it
        # but still delay and record whether they'd be rate limited under the 'test' metric
        allow_usage = True
        _delay_and_report_rate_limit_submission(
            domain, max_wait=max_wait, delay_rather_than_reject=delay_rather_than_reject,
            datadog_metric='commcare.xform_submissions.rate_limited.test',
            limiter=submission_rate_limiter
        )
    else:
        allow_usage = _delay_and_report_rate_limit_submission(
            domain, max_wait=max_wait, delay_rather_than_reject=delay_rather_than_reject,
            datadog_metric='commcare.xform_submissions.rate_limited',
            limiter=submission_rate_limiter
        )

    if allow_form_usage and not allow_case_usage:
        if not DO_NOT_RATE_LIMIT_SUBMISSIONS.enabled(domain):
            allow_usage = _delay_and_report_rate_limit_submission(
                domain, max_wait=max_wait, delay_rather_than_reject=delay_rather_than_reject,
                datadog_metric='commcare.case_updates.rate_limited',
                limiter=domain_case_rate_limiter
            )
        else:
            _delay_and_report_rate_limit_submission(
                domain, max_wait=max_wait, delay_rather_than_reject=delay_rather_than_reject,
                datadog_metric='commcare.case_updates.rate_limited.test',
                limiter=domain_case_rate_limiter
            )
    return not allow_usage


@run_only_when(SHOULD_RATE_LIMIT_SUBMISSIONS)
@silence_and_report_error("Exception raised reporting usage to the submission rate limiter",
                          'commcare.xform_submissions.report_usage_errors')
def report_submission_usage(domain):
    submission_rate_limiter.report_usage(domain)
    global_submission_rate_limiter.report_usage()
    _report_current_global_submission_thresholds()


def report_case_usage(domain, num_cases):
    global_case_rate_limiter.report_usage(delta=num_cases)
    domain_case_rate_limiter.report_usage(scope=domain, delta=num_cases)
    _report_current_global_case_update_thresholds()


def _delay_and_report_rate_limit_submission(domain, max_wait, delay_rather_than_reject, datadog_metric, limiter):
    """
    Attempt to acquire permission from the rate limiter waiting up to 15 seconds.

    When delay_rather_than_reject is False

        If it's acquired, report throttle_method:delay and duration:<bucketed duration>;
        otherwise report throttle_method:reject and duration:delayed_reject or quick_reject,
        depending on whether the rate limiter bothered to wait or could tell there was no chance.

    When delay_rather_than_reject is True

        If it's acquired, report throttle_method:delay and duration:<bucketed duration> (as before);
        otherwise report throttle_method:delay and duration:delay_rather_than_reject

    Returns whether the permission was eventually acquired (with no variation on delay_rather_than_reject).
    """
    with TimingContext() as timer:
        acquired = limiter.wait(domain, timeout=max_wait)
    if acquired:
        duration_tag = bucket_value(timer.duration, [.5, 1, 5, 10, 15], unit='s')
    elif delay_rather_than_reject:
        if timer.duration < max_wait:
            time.sleep(max_wait - timer.duration)
        duration_tag = 'delay_rather_than_reject'
    elif timer.duration < max_wait:
        duration_tag = 'quick_reject'
    else:
        duration_tag = 'delayed_reject'
    metrics_counter(datadog_metric, tags={
        'domain': domain,
        'duration': duration_tag,
        'throttle_method': "delay" if acquired or delay_rather_than_reject else "reject"
    })
    return acquired


@quickcache([], timeout=60)  # Only report up to once a minute
def _report_current_global_submission_thresholds():
    for scope, limits in global_submission_rate_limiter.iter_rates():
        for rate_counter, value, threshold in limits:
            metrics_gauge('commcare.xform_submissions.global_threshold', threshold, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')
            metrics_gauge('commcare.xform_submissions.global_usage', value, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')


@quickcache([], timeout=60)  # Only report up to once a minute
def _report_current_global_case_update_thresholds():
    for scope, limits in global_case_rate_limiter.iter_rates():
        for rate_counter, value, threshold in limits:
            metrics_gauge('commcare.case_updates.global_threshold', threshold, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')
            metrics_gauge('commcare.case_updates.global_usage', value, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')
