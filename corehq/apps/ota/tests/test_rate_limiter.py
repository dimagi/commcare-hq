"""Tests for restore rate limiting dispatch."""
from contextlib import contextmanager
from unittest.mock import patch

from corehq.apps.ota.rate_limiter import (
    rate_limit_restore,
    restore_rate_limiter,
)
from corehq.util.metrics.tests.utils import capture_metrics
from corehq.util.test_utils import flag_disabled, flag_enabled

DOMAIN = 'restore-rate-limit-test'


@contextmanager
def restore_rate_limiters(domain_allowed):
    with (
        patch('corehq.apps.ota.rate_limiter.SHOULD_RATE_LIMIT_RESTORES', True),
        patch.object(restore_rate_limiter, 'allow_usage',
                     return_value=domain_allowed),
        patch.object(restore_rate_limiter, 'report_usage') as report_usage,
    ):
        yield report_usage


def test_restore_with_capacity_is_not_limited():
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(True) as report_usage:
        assert rate_limit_restore(DOMAIN) is False
    report_usage.assert_called_once_with(DOMAIN)


def test_over_limit_restore_is_rate_limited():
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(False) as report_usage:
        assert rate_limit_restore(DOMAIN) is True
    report_usage.assert_not_called()


def test_rate_limited_restore_emits_metric():
    with capture_metrics() as metrics, \
            flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(False):
        rate_limit_restore(DOMAIN)
    assert metrics.list('commcare.restore.rate_limited', domain=DOMAIN)


def test_toggles_off_rate_limited_restore_emits_test_metric():
    with capture_metrics() as metrics, \
            flag_disabled('RATE_LIMIT_RESTORES'), flag_disabled('BLOCK_RESTORES'), \
            restore_rate_limiters(False):
        rate_limit_restore(DOMAIN)
    assert metrics.list('commcare.restore.rate_limited.test', domain=DOMAIN)


def test_block_restores_rejects_regardless_of_capacity():
    with flag_disabled('RATE_LIMIT_RESTORES'), flag_enabled('BLOCK_RESTORES'), \
            restore_rate_limiters(True):
        assert rate_limit_restore(DOMAIN) is True


def test_toggles_off_never_limits_but_still_reports_usage():
    with flag_disabled('RATE_LIMIT_RESTORES'), flag_disabled('BLOCK_RESTORES'), \
            restore_rate_limiters(False) as report_usage:
        assert rate_limit_restore(DOMAIN) is False
    report_usage.assert_called_once_with(DOMAIN)
