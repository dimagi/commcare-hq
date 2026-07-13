from django.conf import settings

from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
    RateLimiter,
    get_dynamic_rate_definition,
)
from corehq.project_limits.shortcuts import (
    delay_and_report_rate_limit,
    get_standard_ratio_rate_definition,
)
from corehq.toggles import RATE_LIMIT_RESTORES, NAMESPACE_DOMAIN, BLOCK_RESTORES
from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.metrics import metrics_counter, metrics_gauge
from corehq.util.quickcache import quickcache

RESTORES_PER_DAY = 3

restore_rate_limiter = RateLimiter(
    feature_key='restores',
    get_rate_limits=lambda domain: _get_per_user_restore_rate_definition(domain)
)


def _get_per_user_restore_rate_definition(domain):
    return PerUserRateDefinition(
        per_user_rate_definition=get_dynamic_rate_definition(
            'restores_per_user',
            default=get_standard_ratio_rate_definition(
                events_per_day=RESTORES_PER_DAY),
        ),
        constant_rate_definition=get_dynamic_rate_definition(
            'baseline_restores_per_project',
            default=RateDefinition(
                per_week=50,
                per_day=25,
                per_hour=15,
                per_minute=5,
                per_second=1,
            ),
        ),
    ).get_rate_limits(domain)


global_restore_rate_limiter = RateLimiter(
    feature_key='global_restores',
    get_rate_limits=lambda scope: get_dynamic_rate_definition(
        'global_restores',
        # Scaled from the global submission defaults by the
        # restore/submission per-user ratio (3/46)
        default=RateDefinition(
            per_hour=1000,
            per_minute=30,
            per_second=3,
        )
    ).get_rate_limits(),
)


SHOULD_RATE_LIMIT_RESTORES = not settings.ENTERPRISE_MODE and not settings.UNIT_TESTING


@run_only_when(lambda: SHOULD_RATE_LIMIT_RESTORES)
@silence_and_report_error("Exception raised in the restore rate limiter",
                          'commcare.restores.rate_limiter_errors')
def rate_limit_restore(domain, max_wait=15):
    if RATE_LIMIT_RESTORES.enabled(domain, namespace=NAMESPACE_DOMAIN):
        return _rate_limit_restore(domain, max_wait=max_wait)
    elif BLOCK_RESTORES.enabled(domain, namespace=NAMESPACE_DOMAIN):
        return True
    else:
        _rate_limit_restore_test(domain)
        return False


def _allow_restore_usage(domain):
    return (global_restore_rate_limiter.allow_usage()
            or restore_rate_limiter.allow_usage(domain))


def _report_restore_usage(domain):
    restore_rate_limiter.report_usage(domain)
    global_restore_rate_limiter.report_usage()
    _report_current_global_restore_thresholds()


def _rate_limit_restore(domain, max_wait=15):

    allow_usage = _allow_restore_usage(domain)

    if not allow_usage:
        allow_usage = delay_and_report_rate_limit(
            domain, max_wait=max_wait, delay_rather_than_reject=False,
            datadog_metric='commcare.restores.rate_limited',
            limiter=restore_rate_limiter,
        )

    if allow_usage:
        _report_restore_usage(domain)

    return not allow_usage


def _rate_limit_restore_test(domain):
    if not _allow_restore_usage(domain):
        metrics_counter('commcare.restores.rate_limited.test', tags={
            'domain': domain,
        })
    _report_restore_usage(domain)


@quickcache([], timeout=60)  # Only report up to once a minute
def _report_current_global_restore_thresholds():
    for scope, limits in global_restore_rate_limiter.iter_rates():
        for rate_counter, value, threshold in limits:
            metrics_gauge('commcare.restores.global_threshold', threshold, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')
            metrics_gauge('commcare.restores.global_usage', value, tags={
                'window': rate_counter.key,
                'scope': scope
            }, multiprocess_mode='max')
