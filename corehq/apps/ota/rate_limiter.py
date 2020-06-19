from django.conf import settings

from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
    RateLimiter,
)
from corehq.project_limits.shortcuts import get_standard_ratio_rate_definition
from corehq.toggles import RATE_LIMIT_RESTORES, NAMESPACE_DOMAIN
from corehq.util.decorators import run_only_when, silence_and_report_error
from corehq.util.metrics import metrics_counter

RESTORES_PER_DAY = 3

restore_rate_limiter = RateLimiter(
    feature_key='restores',
    get_rate_limits=PerUserRateDefinition(
        per_user_rate_definition=get_standard_ratio_rate_definition(
            events_per_day=RESTORES_PER_DAY),
        constant_rate_definition=RateDefinition(
            per_week=50,
            per_day=25,
            per_hour=15,
            per_minute=5,
            per_second=1,
        ),
    ).get_rate_limits
)


SHOULD_RATE_LIMIT_RESTORES = not settings.ENTERPRISE_MODE and not settings.UNIT_TESTING


@run_only_when(SHOULD_RATE_LIMIT_RESTORES)
@silence_and_report_error("Exception raised in the restore rate limiter",
                          'commcare.restores.rate_limiter_errors')
def rate_limit_restore(domain):
    if RATE_LIMIT_RESTORES.enabled(domain, namespace=NAMESPACE_DOMAIN):
        return _rate_limit_restore(domain)
    else:
        _rate_limit_restore_test(domain)
        return False


def _rate_limit_restore(domain):

    allow_usage = restore_rate_limiter.allow_usage(domain)

    if allow_usage:
        restore_rate_limiter.report_usage(domain)
    else:
        metrics_counter('commcare.restore.rate_limited', tags={
            'domain': domain,
        })

    return not allow_usage


def _rate_limit_restore_test(domain):
    if not restore_rate_limiter.allow_usage(domain):
        metrics_counter('commcare.restore.rate_limited.test', tags={
            'domain': domain,
        })
    restore_rate_limiter.report_usage(domain)
