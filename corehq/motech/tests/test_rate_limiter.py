from unittest import TestCase
from unittest.mock import patch

from corehq.motech.rate_limiter import _allow_repeater
from corehq.util.test_utils import flag_enabled


@patch('corehq.motech.rate_limiter.metrics_counter')
@patch('corehq.motech.rate_limiter.repeater_rate_limiter.allow_usage')
@patch('corehq.motech.rate_limiter.repeater_attempts_rate_limiter.allow_usage')
@patch('corehq.motech.rate_limiter.global_repeater_rate_limiter.allow_usage')
class TestRateLimitRepeater(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'test-domain'
        cls.repeater_id = 'test-repeater-id'

    @flag_enabled('RATE_LIMIT_REPEATER_ATTEMPTS')
    def test_rate_limited_by_all(self, global_allowed, repeater_attempts_allowed, repeater_allowed,
                                 metrics_counter):
        global_allowed.return_value = False
        repeater_attempts_allowed.return_value = False
        repeater_allowed.return_value = False
        assert not _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_called_once()

    def test_not_global_rate_limited_and_no_attempts_check(self, global_allowed, repeater_attempts_allowed,
                                                           repeater_allowed, metrics_counter):
        global_allowed.return_value = False

        # rate limited based on repeater rate limiting
        repeater_allowed.return_value = True
        assert _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_not_called()
        repeater_attempts_allowed.assert_not_called()

        repeater_allowed.return_value = False
        assert not _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_called_once()
        repeater_attempts_allowed.assert_not_called()

    @flag_enabled('RATE_LIMIT_REPEATER_ATTEMPTS')
    def test_not_global_rate_limited_and_not_overlimit(self, global_allowed, repeater_attempts_allowed,
                                                       repeater_allowed, metrics_counter):
        global_allowed.return_value = True
        repeater_attempts_allowed.return_value = True
        repeater_allowed.return_value = False  # set this to False to ensure this is not used

        # rate limited based on global and repeater attempts
        assert _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_not_called()
        repeater_attempts_allowed.assert_called_once()

    @flag_enabled('RATE_LIMIT_REPEATER_ATTEMPTS')
    def test_not_global_rate_limited_but_overlimit(self, global_allowed, repeater_attempts_allowed,
                                                   repeater_allowed, metrics_counter):
        global_allowed.return_value = True
        repeater_attempts_allowed.return_value = False

        # rate limited based on repeater
        repeater_allowed.return_value = True
        assert _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_not_called()
        repeater_attempts_allowed.assert_called_once()

        repeater_allowed.return_value = False
        assert not _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_called_once()
        assert repeater_attempts_allowed.call_count == 2

    def test_repeater_rate_limited(self, global_allowed, repeater_attempts_allowed, repeater_allowed,
                                   metrics_counter):
        global_allowed.return_value = False

        repeater_allowed.return_value = True
        assert _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_not_called()

        repeater_allowed.return_value = False
        assert not _allow_repeater(self.domain, self.repeater_id)
        metrics_counter.assert_called_once()
