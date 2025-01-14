from datetime import datetime, timezone

from django.conf import settings
from django_redis import get_redis_connection

from corehq import toggles
from corehq.apps.cloudcare.const import DEVICE_ID as CLOUDCARE_DEVICE_ID
from corehq.util.metrics import metrics_counter, metrics_histogram

DEVICE_RATE_LIMIT_MESSAGE = "Current usage for this user is too high. Please try again in a minute."
DEVICE_SET_CACHE_TIMEOUT = 2 * 60  # 2 minutes


class DeviceRateLimiter:
    """
    Operates on a time window of 1 minute
    """

    def __init__(self):
        # need to use raw redis connection to use srem and scard functions
        self.client = get_redis_connection()

    def device_limit_per_user(self, domain):
        if toggles.INCREASE_DEVICE_LIMIT_PER_USER.enabled(domain):
            return settings.INCREASED_DEVICE_LIMIT_PER_USER
        return settings.DEVICE_LIMIT_PER_USER

    def rate_limit_device(self, domain, user_id, device_id):
        """
        Returns boolean representing if this user_id + device_id combo is rate limited or not
        NOTE: calling this method will result in the device_id being added to the list of used device_ids
        """
        if not device_id or self._is_formplayer(device_id):
            # do not track formplayer activity
            return False

        key = self._get_redis_key(user_id)

        if not self._exists(key):
            self._track_usage(key, device_id, is_key_new=True)
            return False

        if self._device_has_been_used(key, device_id):
            return False

        device_count = self._device_count(key)
        if device_count < self.device_limit_per_user(domain):
            self._track_usage(key, device_id)
            # this intentionally doesn't capture users with 1 device, only those with multiple
            metrics_histogram(
                'commcare.devices_per_user.device_count',
                device_count + 1,
                bucket_tag='count',
                buckets=[3, 5, 8, 10],
                tags={'domain': domain, 'user_id': user_id},
            )
            return False

        metrics_counter(
            'commcare.devices_per_user.rate_limit_exceeded', tags={'domain': domain, 'user_id': user_id}
        )
        return True

    def _get_redis_key(self, user_id):
        """
        Create a redis key using the user_id and current time to the floored minute
        This ensures a new key is used every minute
        """
        time = datetime.now(timezone.utc)
        formatted_time = time.strftime('%Y-%m-%d_%H:%M')
        key = f"device-limiter_{user_id}_{formatted_time}"
        return key

    def _track_usage(self, redis_key, device_id, is_key_new=False):
        self.client.sadd(redis_key, device_id)
        if is_key_new:
            self.client.expire(redis_key, DEVICE_SET_CACHE_TIMEOUT)

    def _device_has_been_used(self, redis_key, device_id):
        # check if device_id is member of the set for this key
        return self.client.srem(redis_key, device_id)

    def _device_count(self, redis_key):
        return self.client.scard(redis_key)

    def _exists(self, redis_key):
        return self.client.exists(redis_key)

    def _is_formplayer(self, device_id):
        return device_id.startswith("WebAppsLogin") or device_id == CLOUDCARE_DEVICE_ID


device_rate_limiter = DeviceRateLimiter()
