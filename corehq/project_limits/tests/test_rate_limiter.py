from unittest.mock import Mock, patch

from testil import eq

from corehq.project_limits.rate_counter.presets import (
    second_rate_counter,
    week_rate_counter,
)
from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
    RateLimiter,
)


@patch('corehq.project_limits.rate_limiter.get_n_users_in_domain', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter.get_n_users_in_subscription', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter._get_account_name', lambda domain: 'test')
def test_rate_limit_interface():
    """
    Just test that very basic usage doesn't error
    """
    per_user_rate_def = RateDefinition(per_week=50000, per_day=13000, per_second=.001)
    min_rate_def = RateDefinition(per_second=10)
    per_user_rate_def = PerUserRateDefinition(per_user_rate_def, min_rate_def)
    my_feature_rate_limiter = RateLimiter('my_feature', per_user_rate_def.get_rate_limits)
    if my_feature_rate_limiter.allow_usage('my_domain'):
        # ...do stuff...
        my_feature_rate_limiter.report_usage('my_domain')


@patch('corehq.project_limits.rate_limiter.get_n_users_in_domain', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter.get_n_users_in_subscription', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter._get_account_name', lambda domain: 'test')
def test_rate_limit_interface_wait_time_for_access():
    """
    Just test that very basic usage doesn't error
    """
    per_user_rate_def = RateDefinition(per_week=50000, per_day=13000, per_second=.001)
    min_rate_def = RateDefinition(per_second=10)
    per_user_rate_def = PerUserRateDefinition(per_user_rate_def, min_rate_def)
    my_feature_rate_limiter = RateLimiter('my_feature', per_user_rate_def.get_rate_limits)

    if my_feature_rate_limiter.get_wait_time_for_access('my_domain') == 0:
        # ...do stuff...
        my_feature_rate_limiter.report_usage('my_domain')


@patch('corehq.project_limits.rate_limiter.get_n_users_in_domain', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter.get_n_users_in_subscription', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter._get_account_name', lambda domain: 'test')
def test_get_window_of_first_exceeded_limit():
    per_user_rate_def = RateDefinition(per_second=10)
    min_rate_def = RateDefinition(per_second=100)
    per_user_rate_def = PerUserRateDefinition(per_user_rate_def, min_rate_def)
    rate_limiter = RateLimiter('my_feature', per_user_rate_def.get_rate_limits)
    rate_limiter.iter_rates = Mock(return_value=[('', [(second_rate_counter, 11, 10)])])
    expected_window = 'second'
    actual_window = rate_limiter.get_window_of_first_exceeded_limit('my_domain')
    eq(actual_window, expected_window)


@patch('corehq.project_limits.rate_limiter.get_n_users_in_domain', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter.get_n_users_in_subscription', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter._get_account_name', lambda domain: 'test')
def test_get_window_of_first_exceeded_limit_none():
    per_user_rate_def = RateDefinition(per_second=10)
    min_rate_def = RateDefinition(per_second=100)
    per_user_rate_def = PerUserRateDefinition(per_user_rate_def, min_rate_def)
    rate_limiter = RateLimiter('my_feature', per_user_rate_def.get_rate_limits)
    rate_limiter.iter_rates = Mock(return_value=[('', [(second_rate_counter, 9, 10)])])
    expected_window = None
    actual_window = rate_limiter.get_window_of_first_exceeded_limit('my_domain')
    eq(actual_window, expected_window)


@patch('corehq.project_limits.rate_limiter.get_n_users_in_domain', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter.get_n_users_in_subscription', lambda domain: 10)
@patch('corehq.project_limits.rate_limiter._get_account_name', lambda domain: 'test')
def test_get_window_of_first_exceeded_limit_priority():
    per_user_rate_def = RateDefinition(per_second=10, per_week=10)
    min_rate_def = RateDefinition(per_second=100)
    per_user_rate_def = PerUserRateDefinition(per_user_rate_def, min_rate_def)
    rate_limiter = RateLimiter('my_feature', per_user_rate_def.get_rate_limits)
    rate_limiter.iter_rates = Mock(return_value=[('', [(week_rate_counter, 11, 10), ('second', 11, 10)])])
    expected_window = 'week'
    actual_window = rate_limiter.get_window_of_first_exceeded_limit('my_domain')
    eq(actual_window, expected_window)
