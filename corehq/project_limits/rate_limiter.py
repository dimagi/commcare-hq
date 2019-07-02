from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import functools

from corehq.project_limits.rate_counter import week_rate_counter, \
    day_rate_counter, hour_rate_counter, minute_rate_counter, second_rate_counter


class RateLimiter(object):
    """
    Example usage:

    >>> MyFeatureRateLimiter = RateLimiter.spawn('my_feature')
    >>> my_feature_rate_limiter = MyFeatureRateLimiter(per_week=50000, per_day=13000,
    ...                                                per_second=5)
    >>> if my_feature_rate_limiter.allow_usage('my_domain'):
    ...     # ...do stuff...
    ...     my_feature_rate_limiter.report_usage('my_domain')

    """
    def __init__(self, feature_key,
                 per_week=None, per_day=None, per_hour=None, per_minute=None, per_second=None):
        self.feature_key = feature_key
        self.rate_limits = [(rate_counter, limit) for limit, rate_counter in (
            (per_week, week_rate_counter),
            (per_day, day_rate_counter),
            (per_hour, hour_rate_counter),
            (per_minute, minute_rate_counter),
            (per_second, second_rate_counter),
        ) if limit]

    @classmethod
    def spawn(cls, feature_key):
        return functools.partial(feature_key)

    def report_usage(self, delta=1, *args):
        scope = (self.feature_key,) + args
        for limit, rate_counter in self.rate_limits:
            rate_counter.increment(scope, delta)

    def allow_usage(self, *args):
        scope = (self.feature_key,) + args
        return all(rate_counter.get(scope) < limit for limit, rate_counter in self.rate_limits)
