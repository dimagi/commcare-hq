from django.conf import settings

from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
    RateLimiter,
)
from corehq.toggles import RATE_LIMIT_RESTORES, NAMESPACE_DOMAIN
from corehq.util.datadog.gauges import datadog_counter
from corehq.util.decorators import run_only_when, silence_and_report_error

restores_per_user = RateDefinition(
    per_week=5.75,
    per_day=1.15,
    per_hour=0.15,
    per_minute=0.0035,
    per_second=0.00025,
)

base_restores_per_domain = RateDefinition(
    per_week=50,
    per_day=25,
    per_hour=15,
    per_minute=5,
    per_second=1,
)

restore_rates = PerUserRateDefinition(
    per_user_rate_definition=restores_per_user,
    constant_rate_definition=base_restores_per_domain,
)

restore_rate_limiter = RateLimiter(
    feature_key='restores',
    get_rate_limits=restore_rates.get_rate_limits
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
        datadog_counter('commcare.restore.rate_limited', tags=[
            'domain:{}'.format(domain),
        ])

    return not allow_usage


def _rate_limit_restore_test(domain):
    if not restore_rate_limiter.allow_usage(domain):
        datadog_counter('commcare.restore.rate_limited.test', tags=[
            'domain:{}'.format(domain),
        ])
    restore_rate_limiter.report_usage(domain)
