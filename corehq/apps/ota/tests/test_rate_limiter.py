"""Tests for restore rate limiting dispatch and rate definitions."""
from contextlib import contextmanager
from unittest.mock import patch

import attr
import pytest

from django.test import TestCase

from corehq.apps.ota.rate_limiter import (
    _get_per_user_restore_rate_definition,
    global_restore_rate_limiter,
    rate_limit_restore,
    restore_rate_limiter,
)
from corehq.project_limits.models import DynamicRateDefinition
from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
)
from corehq.project_limits.shortcuts import get_standard_ratio_rate_definition
from corehq.util.metrics.tests.utils import capture_metrics
from corehq.util.test_utils import flag_disabled, flag_enabled

DOMAIN = 'restore-rate-limit-test'


@attr.s(auto_attribs=True)
class LimiterMocks:
    global_report_usage: object
    domain_report_usage: object
    wait: object


@contextmanager
def restore_rate_limiters(global_allowed, domain_allowed, wait_acquires=False):
    with (
        patch('corehq.apps.ota.rate_limiter.SHOULD_RATE_LIMIT_RESTORES', True),
        patch.object(global_restore_rate_limiter, 'allow_usage',
                     return_value=global_allowed),
        patch.object(restore_rate_limiter, 'allow_usage',
                     return_value=domain_allowed),
        patch.object(restore_rate_limiter, 'wait',
                     return_value=wait_acquires) as wait,
        patch.object(global_restore_rate_limiter, 'report_usage') as global_report_usage,
        patch.object(restore_rate_limiter, 'report_usage') as domain_report_usage,
        patch('corehq.apps.ota.rate_limiter._report_current_global_restore_thresholds'),
    ):
        yield LimiterMocks(global_report_usage, domain_report_usage, wait)


@pytest.mark.parametrize("global_allowed, domain_allowed, wait_acquires, expect_limited", [
    (True, True, False, False),
    # under the global threshold, domain limits don't apply
    (True, False, False, False),
    # over the global threshold, but the domain has capacity
    (False, True, False, False),
    # over all limits, but capacity freed up while waiting
    (False, False, True, False),
    # over all limits and no capacity freed up while waiting
    (False, False, False, True),
])
def test_rate_limit_restore(global_allowed, domain_allowed, wait_acquires, expect_limited):
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(global_allowed, domain_allowed, wait_acquires):
        assert rate_limit_restore(DOMAIN) is expect_limited


def test_restore_with_capacity_does_not_wait():
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(False, True) as mocks:
        rate_limit_restore(DOMAIN)
    mocks.wait.assert_not_called()


def test_over_limit_restore_waits_for_capacity():
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(False, False) as mocks:
        rate_limit_restore(DOMAIN)
    mocks.wait.assert_called_once_with(DOMAIN, timeout=15)


def test_allowed_restore_reports_usage_to_both_limiters():
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(True, False) as mocks:
        rate_limit_restore(DOMAIN)
    mocks.global_report_usage.assert_called_once()
    mocks.domain_report_usage.assert_called_once_with(DOMAIN)


def test_delayed_restore_reports_usage_to_both_limiters():
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(False, False, wait_acquires=True) as mocks:
        rate_limit_restore(DOMAIN)
    mocks.global_report_usage.assert_called_once()
    mocks.domain_report_usage.assert_called_once_with(DOMAIN)


def test_rate_limited_restore_does_not_report_usage():
    with flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(False, False) as mocks:
        rate_limit_restore(DOMAIN)
    mocks.global_report_usage.assert_not_called()
    mocks.domain_report_usage.assert_not_called()


def test_rate_limited_restore_emits_metric():
    with capture_metrics() as metrics, \
            flag_enabled('RATE_LIMIT_RESTORES'), \
            restore_rate_limiters(False, False):
        rate_limit_restore(DOMAIN)
    assert metrics.list('commcare.restore.rate_limited', domain=DOMAIN)


def test_toggles_off_rate_limited_restore_emits_test_metric():
    with capture_metrics() as metrics, \
            flag_disabled('RATE_LIMIT_RESTORES'), flag_disabled('BLOCK_RESTORES'), \
            restore_rate_limiters(False, False):
        rate_limit_restore(DOMAIN)
    assert metrics.list('commcare.restore.rate_limited.test', domain=DOMAIN)


def test_block_restores_rejects_regardless_of_capacity():
    with flag_disabled('RATE_LIMIT_RESTORES'), flag_enabled('BLOCK_RESTORES'), \
            restore_rate_limiters(True, True):
        assert rate_limit_restore(DOMAIN) is True


def test_toggles_off_never_limits_never_waits_but_still_reports_usage():
    with flag_disabled('RATE_LIMIT_RESTORES'), flag_disabled('BLOCK_RESTORES'), \
            restore_rate_limiters(False, False) as mocks:
        assert rate_limit_restore(DOMAIN) is False
    mocks.wait.assert_not_called()
    mocks.global_report_usage.assert_called_once()
    mocks.domain_report_usage.assert_called_once_with(DOMAIN)


class RestoreRateDefinitionDefaultsTest(TestCase):
    """The dynamic rate definitions' defaults preserve the previously
    hardcoded restore limits, and the global limiter gets the agreed
    starting thresholds."""

    def tearDown(self):
        for definition in DynamicRateDefinition.objects.filter(key__in=[
                'restores_per_user', 'baseline_restores_per_project', 'global_restores']):
            # delete one by one to also trigger clearing caches
            definition.delete()
        super().tearDown()

    def test_per_project_defaults_match_previous_hardcoded_values(self):
        with patch('corehq.project_limits.rate_limiter.get_n_users_in_domain',
                   return_value=10), \
                patch('corehq.project_limits.rate_limiter.get_n_users_in_subscription',
                      return_value=100), \
                patch('corehq.project_limits.rate_limiter._get_account_name',
                      return_value='account:test'):
            expected = PerUserRateDefinition(
                per_user_rate_definition=get_standard_ratio_rate_definition(
                    events_per_day=3),
                constant_rate_definition=RateDefinition(
                    per_week=50,
                    per_day=25,
                    per_hour=15,
                    per_minute=5,
                    per_second=1,
                ),
            ).get_rate_limits(DOMAIN)
            actual = _get_per_user_restore_rate_definition(DOMAIN)
        assert actual == expected

    def test_global_restore_defaults(self):
        global_restore_rate_limiter.get_rate_limits('')
        definition = DynamicRateDefinition.objects.get(key='global_restores')
        assert definition.per_week is None
        assert definition.per_day is None
        assert definition.per_hour == 1000
        assert definition.per_minute == 30
        assert definition.per_second == 3
