from datetime import datetime, timedelta
from dimagi.utils.couch.cache.cache_core import get_redis_client


def rate_limit(key, actions_allowed=60, how_often=60):
    """
    A simple util to be used for rate limiting, using redis as a backend.

    key - a unique key which describes the action you are rate limiting

    actions_allowed - the number of actions to allow for key every how_often
    seconds before returning False

    returns True to proceed with the action, or False to not proceed

    For example, to only allow a single project space to send 100 SMS max every
    30 seconds:

    if rate_limit('send-sms-for-projectname', actions_allowed=100, how_often=30):
        <perform action>
    else:
        <delay action>
    """

    # We need access to the raw redis client because calling incr on
    # a django_redis RedisCache object raises an error if the key
    # doesn't exist.
    client = get_redis_client().client.get_client()

    # Increment the key. If they key doesn't exist (or already expired),
    # redis sets the value to 0 before incrementing.
    value = client.incr(key)

    if value == 1 or client.ttl(key) == -1:
        # Set the key's expiration if it's the first action we're granting.
        # As a precauation, we also check to make sure that the key actually has
        # an expiration set in case an error occurred the first time we tried to
        # set the expiration. If it doesn't have an expiration (ttl == -1), then
        # we'll set it here again.
        client.expire(key, how_often)

    return value <= actions_allowed


class DomainRateLimiter(object):
    """
    A util for rate limiting by domain.
    For example, to allow a domain to only send 100 SMS every 60 seconds:

    limiter = DomainRateLimiter('send-sms-for-', 100, 60)
    ...
    if limiter.can_perform_action('my-domain'):
        <perform action>
    else:
        <delay action>
    """
    def __init__(self, key, actions_allowed, how_often):
        """
        key - the beginning of the redis key that will be used to rate limit on;
        the actual key that is used will be key + domain

        actions_allowed - see rate_limit()

        how_often - see rate_limit()
        """
        self.key = key
        self.actions_allowed = actions_allowed
        self.how_often = how_often

        """
        Dictionary of {domain: datetime}
        When a domain exceeds its allowed actions, an entry is put here to
        note the timestamp when the domain should be allowed to perform
        actions again. This is meant to save calls to redis when we know
        a domain is in a "cool down" phase.

        NOTE: Multiple processes might all have their own instance of a
        DomainRateLimiter with the same key, and that's ok, it just means
        each process will make 1 extra call to redis and then stop after that.
        This also doesn't have to be thread safe since dirty reads won't
        affect the overall function of the rate limiter.
        """
        self.cooldown = {}

    def can_perform_action(self, domain):
        """
        Returns True if the action can be performed, False if the action should
        be delayed because the number of allowed actions has been exceeded.
        """
        if domain in self.cooldown and datetime.utcnow() < self.cooldown[domain]:
            return False

        key = self.key + domain
        if rate_limit(key, actions_allowed=self.actions_allowed, how_often=self.how_often):
            return True
        else:
            # Add an entry to self.cooldown so that next time we don't have to
            # make a call to redis
            client = get_redis_client().client.get_client()
            time_remaining = client.ttl(key)
            if time_remaining < 0:
                # If we just happened to time it so that the key just expired or
                # a key was just created but doesn't have a timeout yet, then use a
                # value of 0 here and the cool down will be ignored.
                time_remaining = 0
            self.cooldown[domain] = datetime.utcnow() + timedelta(seconds=time_remaining)
            return False
