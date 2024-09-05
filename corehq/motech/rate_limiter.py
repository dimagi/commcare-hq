from django.conf import settings

from corehq.project_limits.rate_limiter import (
    get_dynamic_rate_definition,
    RateDefinition,
    PerUserRateDefinition,
    RateLimiter,
)
from corehq.toggles import RATE_LIMIT_REPEATERS, RATE_LIMIT_REPEATER_ATTEMPTS, NAMESPACE_DOMAIN
from corehq.util.decorators import silence_and_report_error, run_only_when
from corehq.util.metrics import metrics_gauge, metrics_counter
from corehq.util.quickcache import quickcache

repeater_rate_limiter = RateLimiter(
    feature_key='repeater_wait_milliseconds',
    get_rate_limits=lambda domain: _get_per_user_repeater_wait_milliseconds_rate_definition(domain)
)


def _get_per_user_repeater_wait_milliseconds_rate_definition(domain):
    return PerUserRateDefinition(
        per_user_rate_definition=get_dynamic_rate_definition(
            'repeater_wait_milliseconds_per_user',
            default=RateDefinition(
                per_week=3000,
                per_day=600,
                per_hour=30,
                per_minute=0.6,
                per_second=None,
            ).times(1000),
        ),
        constant_rate_definition=get_dynamic_rate_definition(
            'repeater_wait_milliseconds',
            default=RateDefinition(
                per_week=0,
                per_day=0,
                per_hour=0,
                per_minute=0,
                per_second=None,
            ),
        ),
    ).get_rate_limits(domain)


global_repeater_rate_limiter = RateLimiter(
    feature_key='global_repeater_wait_milliseconds',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'global_repeater_wait_milliseconds',
        default=RateDefinition(
            per_hour=360000,
            per_minute=6000,
            per_second=100,
        ).times(1000)
    ).get_rate_limits(),
)


repeater_attempts_rate_limiter = RateLimiter(
    feature_key='repeater_attempts',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        "repeater_attempts",
        default=RateDefinition(
            per_week=None,
            per_day=None,
            per_hour=360000,
            per_minute=6000,
            per_second=100,
        ),
    ).get_rate_limits(),
)


SHOULD_RATE_LIMIT_REPEATERS = not settings.UNIT_TESTING


@run_only_when(SHOULD_RATE_LIMIT_REPEATERS)
@silence_and_report_error("Exception raised in the repeater rate limiter",
                          'commcare.repeaters.rate_limiter_errors')
def rate_limit_repeater(domain, repeater_id):
    limit_attempts = RATE_LIMIT_REPEATER_ATTEMPTS.enabled(domain, namespace=NAMESPACE_DOMAIN)
    is_under_attempt_limit = repeater_attempts_rate_limiter.allow_usage(repeater_id) if limit_attempts else True

    if global_repeater_rate_limiter.allow_usage() and is_under_attempt_limit:
        allow_usage = True
    elif repeater_rate_limiter.allow_usage(domain):
        allow_usage = True
    elif not RATE_LIMIT_REPEATERS.enabled(domain, namespace=NAMESPACE_DOMAIN):
        allow_usage = True
        metrics_counter('commcare.repeaters.rate_limited.test', tags={
            'domain': domain,
        })
    else:
        allow_usage = False
        metrics_counter('commcare.repeaters.rate_limited', tags={
            'domain': domain,
        })

    return not allow_usage


@run_only_when(SHOULD_RATE_LIMIT_REPEATERS)
@silence_and_report_error("Exception raised reporting usage to the repeater rate limiter",
                          'commcare.repeaters.report_usage_errors')
def report_repeater_usage(domain, milliseconds):
    repeater_rate_limiter.report_usage(domain, delta=milliseconds)
    global_repeater_rate_limiter.report_usage(delta=milliseconds)
    _report_current_global_repeater_thresholds()


@run_only_when(SHOULD_RATE_LIMIT_REPEATERS)
@silence_and_report_error("Exception raised reporting usage to the repeater attempt rate limiter",
                          'commcare.repeaters.report_usage_errors')
def report_repeater_attempt(repeater_id):
    repeater_attempts_rate_limiter.report_usage(repeater_id)


@quickcache([], timeout=60)  # Only report up to once a minute
def _report_current_global_repeater_thresholds():
    for scope, limits in global_repeater_rate_limiter.iter_rates():
        for rate_counter, value, threshold in limits:
            metrics_gauge('commcare.repeaters.global_threshold', threshold, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')
            metrics_gauge('commcare.repeaters.global_usage', value, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')
