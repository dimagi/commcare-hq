from django.test import SimpleTestCase, override_settings
from freezegun import freeze_time

from corehq.apps.cloudcare.const import DEVICE_ID as CLOUDCARE_DEVICE_ID
from corehq.apps.users.device_rate_limiter import device_rate_limiter
from corehq.tests.pytest_plugins.reusedb import clear_redis
from corehq.util.test_utils import flag_enabled


@freeze_time("2024-12-10 12:05:43")
@override_settings(DEVICE_LIMIT_PER_USER=1)
@override_settings(ENABLE_DEVICE_RATE_LIMITER=True)
class TestDeviceRateLimiter(SimpleTestCase):

    domain = 'device-rate-limit-test'

    def setUp(self):
        self.addCleanup(clear_redis)

    def test_allowed_if_no_devices_have_been_used_yet(self):
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))

    @override_settings(DEVICE_LIMIT_PER_USER=2)
    def test_allowed_if_device_count_is_under_limit(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))

    def test_rate_limited_if_device_count_exceeds_limit(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertTrue(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))

    def test_allowed_if_device_has_already_been_used(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id'))

    def test_allowed_if_different_user(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'new-user-id', 'existing-device-id'))

    def test_allowed_after_waiting_one_minute(self):
        with freeze_time("2024-12-10 12:05:43") as frozen_time:
            device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
            self.assertTrue(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))
            frozen_time.move_to("2024-12-10 12:06:15")
            self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))

    def test_formplayer_activity_is_always_allowed(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'WebAppsLogin*newlogin'))
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', CLOUDCARE_DEVICE_ID))

    def test_formplayer_activity_does_not_count_towards_limit(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'WebAppsLogin*newlogin')
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', CLOUDCARE_DEVICE_ID)
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))

    @override_settings(DEVICE_LIMIT_PER_USER=1)
    @override_settings(INCREASED_DEVICE_LIMIT_PER_USER=2)
    def test_allowed_after_enabling_ff_to_increase_limit(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertTrue(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))
        with flag_enabled('INCREASE_DEVICE_LIMIT_PER_USER'):
            self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))

    @override_settings(ENABLE_DEVICE_RATE_LIMITER=False)
    def test_allowed_if_rate_limiter_is_disabled(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'new-device-id'))

    def test_allowed_if_user_id_or_device_id_is_none(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, 'user-id', None))
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, None, 'new-device-id'))

    def test_domains_do_not_conflict(self):
        device_rate_limiter.rate_limit_device(self.domain, 'user-id', 'existing-device-id')
        device_rate_limiter.rate_limit_device('random-domain', 'user-id', 'random-device')
        self.assertTrue(device_rate_limiter.rate_limit_device('random-domain', 'user-id', 'existing-device-id'))
