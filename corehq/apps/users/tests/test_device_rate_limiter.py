from django.test import TestCase
from freezegun import freeze_time

from corehq.apps.cloudcare.const import DEVICE_ID as CLOUDCARE_DEVICE_ID
from corehq.apps.users.device_rate_limiter import DEVICE_LIMIT_PER_USER_KEY, REDIS_KEY_PREFIX, device_rate_limiter
from corehq.apps.users.models import CommCareUser
from corehq.project_limits.models import SystemLimit
from corehq.util.test_utils import flag_disabled, flag_enabled


@freeze_time("2024-12-10 12:05:43")
@flag_enabled("DEVICE_RATE_LIMITER")
class TestDeviceRateLimiter(TestCase):

    domain = 'device-rate-limit-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = CommCareUser.create(cls.domain, 'test-mobile-user', 'abc123', None, None)
        cls.addClassCleanup(cls.user.delete, None, None)

    def setUp(self):
        SystemLimit.objects.create(key=DEVICE_LIMIT_PER_USER_KEY, limit=1)
        self.addCleanup(self._cleanup_redis)

    def _cleanup_redis(self):
        for key in device_rate_limiter.client.scan_iter(f"{REDIS_KEY_PREFIX}*"):
            device_rate_limiter.client.delete(key.decode('utf-8'))

    def test_allowed_if_no_devices_have_been_used_yet(self):
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    def test_allowed_if_device_count_is_under_limit(self):
        SystemLimit.objects.update_or_create(defaults={"limit": 2}, key=DEVICE_LIMIT_PER_USER_KEY)
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    def test_rate_limited_if_device_count_exceeds_limit(self):
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertTrue(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    def test_allowed_if_device_has_already_been_used(self):
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id'))

    def test_allowed_if_different_user(self):
        new_user = CommCareUser.create(self.domain, 'new-test-mobile-user', 'abc123', None, None)
        self.addCleanup(new_user.delete, None, None)
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, new_user, 'existing-device-id'))

    def test_allowed_after_waiting_one_minute(self):
        with freeze_time("2024-12-10 12:05:43") as frozen_time:
            device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
            self.assertTrue(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))
            frozen_time.move_to("2024-12-10 12:06:15")
            self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    def test_formplayer_activity_is_always_allowed(self):
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'WebAppsLogin*newlogin'))
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, CLOUDCARE_DEVICE_ID))

    def test_formplayer_activity_does_not_count_towards_limit(self):
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'WebAppsLogin*newlogin')
        device_rate_limiter.rate_limit_device(self.domain, self.user, CLOUDCARE_DEVICE_ID)
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    def test_domain_has_higher_limit(self):
        SystemLimit.objects.create(key=DEVICE_LIMIT_PER_USER_KEY, limit=2, domain=self.domain)

        device_rate_limiter.rate_limit_device('random-domain', self.user, 'existing-device-id')
        self.assertTrue(device_rate_limiter.rate_limit_device('random-domain', self.user, 'new-device-id'))

        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    def test_domain_has_lower_limit(self):
        SystemLimit.objects.update_or_create(defaults={"limit": 2}, key=DEVICE_LIMIT_PER_USER_KEY)
        SystemLimit.objects.create(key=DEVICE_LIMIT_PER_USER_KEY, limit=1, domain=self.domain)

        device_rate_limiter.rate_limit_device('random-domain', self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device('random-domain', self.user, 'new-device-id'))

        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertTrue(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    @flag_disabled("DEVICE_RATE_LIMITER")
    def test_allowed_if_rate_limiter_is_disabled(self):
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, 'new-device-id'))

    def test_allowed_if_user_or_device_id_is_none(self):
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, self.user, None))
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, None, 'new-device-id'))

    def test_domains_do_not_conflict(self):
        device_rate_limiter.rate_limit_device(self.domain, self.user, 'existing-device-id')
        device_rate_limiter.rate_limit_device('random-domain', self.user, 'random-device')
        self.assertTrue(device_rate_limiter.rate_limit_device('random-domain', self.user, 'existing-device-id'))

    def test_demo_user_activity_is_not_limited(self):
        demo_user = CommCareUser.create(self.domain, 'test-demo-user', 'abc123', None, None)
        demo_user.is_demo_user = True
        demo_user.save()
        self.addCleanup(demo_user.delete, None, None)
        device_rate_limiter.rate_limit_device(self.domain, demo_user, 'existing-device-id')
        self.assertFalse(device_rate_limiter.rate_limit_device(self.domain, demo_user, 'new-device-id'))
