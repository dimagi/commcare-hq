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
