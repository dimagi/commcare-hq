import logging
from datetime import datetime, timezone

from django_redis import get_redis_connection

from corehq import toggles
from corehq.apps.cloudcare.const import DEVICE_ID as CLOUDCARE_DEVICE_ID
from corehq.project_limits.models import SystemLimit
from corehq.util.metrics import metrics_counter

logger = logging.getLogger(__name__)

DEVICE_RATE_LIMIT_MESSAGE = "Current usage for this user is too high. Please try again in a minute."
# intentionally set to > 1 minute to allow for a buffer at minute boundaries
DEVICE_SET_CACHE_TIMEOUT = 2 * 60  # 2 minutes

DEVICE_LIMIT_PER_USER_KEY = "device_limit_per_user"
DEVICE_LIMIT_PER_USER_DEFAULT = 50
REDIS_KEY_PREFIX = "device-limiter"


class DeviceRateLimiter:
    """
    Operates on a time window of 1 minute
    """

    def __init__(self):
        # need to use raw redis connection to use sismember and scard functions
        self.client = get_redis_connection()

    def device_limit_per_user(self, domain):
        return SystemLimit.for_key(DEVICE_LIMIT_PER_USER_KEY, domain=domain) or DEVICE_LIMIT_PER_USER_DEFAULT

    def rate_limit_device(self, domain, user, device_id):
        """
        Returns boolean representing if this user_id + device_id combo is rate limited or not
        NOTE: calling this method will result in the device_id being added to the list of used device_ids
        """
        if not device_id or not user:
            logger.info(
                f"Unable to rate limit device activity for domain {domain}, user {user.user_id if user else None},"
                f" and device {device_id}"
            )
            return False

        if user.is_commcare_user() and user.is_demo_user:
            # demo users are intended to be used across devices
            return False

        if self._is_formplayer(device_id):
            # do not track formplayer activity
            return False

        key = self._get_redis_key(domain, user.user_id)

        key_exists, device_exists, device_count = self._get_usage_for_device(key, device_id)

        if not key_exists:
            self._track_usage(key, device_id, is_key_new=True)
            return False

        if device_exists:
            return False

        if device_count < self.device_limit_per_user(domain):
            self._track_usage(key, device_id)
            return False

        is_enabled = toggles.DEVICE_RATE_LIMITER.enabled(domain, toggles.NAMESPACE_DOMAIN)
        metrics_counter(
            'commcare.devices_per_user.rate_limited',
            tags={'domain': domain, 'user_id': user.user_id, 'enabled': str(is_enabled)},
        )
        return is_enabled

    def _get_redis_key(self, domain, user_id):
        """
        Create a redis key using the domain, user_id, and current time to the floored minute
        This ensures a new key is used every minute
        """
        time = datetime.now(timezone.utc)
        formatted_time = time.strftime('%Y-%m-%d_%H:%M')
        key = f"{REDIS_KEY_PREFIX}_{domain}_{user_id}_{formatted_time}"
        return key

    def _track_usage(self, redis_key, device_id, is_key_new=False):
        pipe = self.client.pipeline()
        pipe.sadd(redis_key, device_id)
        if is_key_new:
            pipe.expire(redis_key, DEVICE_SET_CACHE_TIMEOUT)
        pipe.execute()

    def _get_usage_for_device(self, redis_key, device_id):
        pipe = self.client.pipeline()
        pipe.exists(redis_key)
        pipe.sismember(redis_key, device_id)
        pipe.scard(redis_key)
        return pipe.execute()

    def _is_formplayer(self, device_id):
        return device_id.startswith("WebAppsLogin") or device_id == CLOUDCARE_DEVICE_ID


device_rate_limiter = DeviceRateLimiter()
