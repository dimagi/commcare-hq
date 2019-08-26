from mock import mock

from corehq.project_limits.rate_limiter import RateLimiter, RateDefinition, \
    PerUserRateDefinition


@mock.patch('corehq.project_limits.rate_limiter.get_user_count', lambda domain: 10)
def test_rate_limit_interface():
    """
    Just test that very basic usage doesn't error
    """
    per_user_rate_def = RateDefinition(per_week=50000, per_day=13000, per_second=.001)
    min_rate_def = RateDefinition(per_second=10)
    my_feature_rate_limiter = RateLimiter('my_feature', PerUserRateDefinition(per_user_rate_def, min_rate_def).get_rate_limits)
    if my_feature_rate_limiter.allow_usage('my_domain'):
        # ...do stuff...
        my_feature_rate_limiter.report_usage('my_domain')
