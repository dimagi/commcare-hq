import random
import time

import attr

from corehq.apps.users.models import CommCareUser
from corehq.project_limits.models import DynamicRateDefinition
from corehq.project_limits.rate_counter.presets import (
    day_rate_counter,
    hour_rate_counter,
    minute_rate_counter,
    second_rate_counter,
    week_rate_counter,
)
from corehq.util.metrics import metrics_counter
from corehq.util.quickcache import quickcache


class RateLimiter(object):
    """
    Example usage:

    >>> per_user_rate_def = RateDefinition(per_week=50000, per_day=13000, per_second=.001)
    >>> min_rate_def = RateDefinition(per_second=10)
    >>> per_user_rate_def = PerUserRateDefinition(per_user_rate_def, min_rate_def)
    >>> my_feature_rate_limiter = RateLimiter('my_feature', per_user_rate_def.get_rate_limits)
    >>> if my_feature_rate_limiter.allow_usage('my_domain'):
    ...     # ...do stuff...
    ...     my_feature_rate_limiter.report_usage('my_domain')

    """
    def __init__(self, feature_key, get_rate_limits):
        self.feature_key = feature_key
        self.get_rate_limits = get_rate_limits

    def report_usage(self, scope='', delta=1):
        for limit_scope, limits in self.get_rate_limits(scope):
            for rate_counter, limit in limits:
                rate_counter.increment(self.feature_key + limit_scope, delta=delta)

    def get_window_of_first_exceeded_limit(self, scope=''):
        for _limit_scope, rates in self.iter_rates(scope):
            for rate_counter, current_rate, limit in rates:
                if current_rate >= limit:
                    return rate_counter.key

        return None

    def allow_usage(self, scope=''):
        allowed = False
        # allow usage if any scope has capacity
        for _limit_scope, rates in self.iter_rates(scope):
            allow = all(current_rate < limit
                        for _rate_counter, current_rate, limit in rates)
            # for each scope all counters must be below threshold
            if allow:
                allowed = True
            else:
                metrics_counter('commcare.rate_limit_exceeded', tags={'key': self.feature_key, 'scope': scope})
        return allowed

    def get_retry_after(self, scope):
        """
        Returns the minimum amount of seconds until additional capacity becomes available again
        """
        seconds_per_scope = {}
        for scope, rates in self.iter_rates(scope):
            seconds_per_scope[scope] = 0.0
            for rate_counter, current_rate, limit in rates:
                if current_rate >= limit:
                    seconds_per_scope[scope] = max(seconds_per_scope[scope], rate_counter.retry_after())
        retry_after_values = seconds_per_scope.values()
        return min(retry_after_values)

    def iter_rates(self, scope=''):
        """
        Get generator of tuples for each set of limits returned by `get_rate_limits`, where the first item
        of the tuple is the normalized scope, and the second is a generator of
        (rate_counter (obj), current rate, rate limit) for each limit in that scope

        e.g.
        ('test-domain', [
            (rate_counter, 92359, 115000)
            (rate_counter, ...)
            ...
        ])
        where `rate_counter.key` is the window of the counter i.e. 'week', 'day' etc
        """

        for limit_scope, limits in self.get_rate_limits(scope):
            yield (
                limit_scope,
                ((rate_counter, rate_counter.get(self.feature_key + limit_scope), limit)
                for rate_counter, limit in limits)
            )

    def wait(self, scope, timeout, windows_not_to_wait_on=('hour', 'day', 'week')):
        start = time.time()
        target_end = start + timeout
        delay = 0
        larger_windows_allow = all(
            current_rate < limit
            for limit_scope, limits in self.iter_rates(scope)
            for rate_counter, current_rate, limit in limits
            if rate_counter.key in windows_not_to_wait_on
        )
        if not larger_windows_allow:
            # There's no point in waiting 15 seconds for the hour/day/week values to change
            return False

        while True:
            if self.allow_usage(scope):
                return True
            # add a random amount between 100ms and 500ms to the last delay
            # so that the delays get a bit longer each time
            # and different requests don't have exactly the same schedule
            delay += random.uniform(0.1, 0.5)
            # if the delay would bring us past the timeout
            # rescheduled for right at the timeout instead
            delay = min(delay, target_end - time.time())
            if delay < 0.01:
                return False
            else:
                time.sleep(delay)


@quickcache(['domain'], memoize_timeout=60, timeout=60 * 60)
def get_n_users_in_domain(domain):
    return CommCareUser.total_by_domain(domain, is_active=True)


@quickcache(['domain'], memoize_timeout=60, timeout=60 * 60)
def get_n_users_in_subscription(domain):
    from corehq.apps.accounting.models import Subscription
    subscription = Subscription.get_active_subscription_by_domain(domain)
    if subscription:
        plan_version = subscription.plan_version
        return plan_version.feature_rates.get(feature__feature_type='User').monthly_limit
    else:
        return 0


@quickcache(['domain'], memoize_timeout=60, timeout=60 * 60)
def _get_account_name(domain):
    from corehq.apps.accounting.models import BillingAccount
    account = BillingAccount.get_account_by_domain(domain)
    if account is not None:
        return f'account:{account.name}'
    else:
        return f'no_account:{domain}'


class PerUserRateDefinition(object):
    def __init__(self, per_user_rate_definition, constant_rate_definition=None):
        self.per_user_rate_definition = per_user_rate_definition
        self.constant_rate_definition = constant_rate_definition or RateDefinition()

    def get_rate_limits(self, domain):
        domain_users = get_n_users_in_domain(domain)
        enterprise_users = get_n_users_in_subscription(domain)
        limit_pairs = [
            (domain_users, domain),
            (enterprise_users, _get_account_name(domain))
        ]
        limits = []
        for n_users, scope_key in limit_pairs:
            domain_limit = (
                self.per_user_rate_definition
                .times(n_users)
                .plus(self.constant_rate_definition)
            ).get_rate_limits(scope_key)
            limits.extend(domain_limit)
        return limits


@attr.s
class RateDefinition(object):
    per_week = attr.ib(default=None)
    per_day = attr.ib(default=None)
    per_hour = attr.ib(default=None)
    per_minute = attr.ib(default=None)
    per_second = attr.ib(default=None)

    def times(self, multiplier):
        return self.map(lambda value: value * multiplier if value is not None else value)

    def plus(self, other):
        return self.map(lambda value, other_value:
                        None if value is None else value + (other_value or 0), other)

    def map(self, math_func, other=None):
        """
        Create new rate definition object with math_func applied to each value of self

        This is essentially RateDefinition(per_week=math_func(self.per_week), ...)
        but deals better with None values and uses meta-programming to avoid copy-paste errors.
        """
        kwargs = {}
        for attribute in self.__attrs_attrs__:
            value = getattr(self, attribute.name)
            if other:
                other_value = getattr(other, attribute.name)
                kwargs[attribute.name] = math_func(value, other_value)
            else:
                kwargs[attribute.name] = math_func(value)
        return self.__class__(**kwargs)

    def get_rate_limits(self, scope=''):
        return [(scope, [(rate_counter, limit) for limit, rate_counter in (
            # order matters for returning the highest priority window
            (self.per_week, week_rate_counter),
            (self.per_day, day_rate_counter),
            (self.per_hour, hour_rate_counter),
            (self.per_minute, minute_rate_counter),
            (self.per_second, second_rate_counter),
        ) if limit])]


@quickcache(['key'], timeout=24 * 60 * 60)
def get_dynamic_rate_definition(key, default):
    dynamic_rate_definition, _ = DynamicRateDefinition.objects.get_or_create(
        key=key, defaults=_get_rate_definition_dict(default))
    return rate_definition_from_db_object(dynamic_rate_definition)


def rate_definition_from_db_object(dynamic_rate_definition):
    return RateDefinition(**_get_rate_definition_dict(dynamic_rate_definition))


def _get_rate_definition_dict(rate_definition):
    """
    Convert RateDefinition-like object to dict like {'per_week': ..., 'per_hour': ..., ...}
    """
    return {
        attribute.name: getattr(rate_definition, attribute.name)
        for attribute in RateDefinition.__attrs_attrs__
    }
