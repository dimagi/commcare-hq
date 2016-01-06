from dimagi.utils.couch.cache.cache_core import get_redis_client


def load_balance(key, objects):
    """
    A util to be used for simple round-robin load balancing, using redis
    as a backend.

    key - a unique key across redis which describes the action you are
          load balancing

    objects - a list of objects (servers, phone numbers, etc.) over which
              you are balancing the load

    Returns the next object in the list to use

    For example, to balance the load among 3 outbound phone numbers when
    sending SMS, you could use the phone number returned by:

    load_balance('outbound-phone-number', ['16175550001', '16175550002', '16175550003'])
    """

    # We need access to the raw redis client because calling incr on
    # a django_redis RedisCache object raises an error if the key
    # doesn't exist.
    client = get_redis_client().client.get_client()

    # Increment the key. If they key doesn't exist (or already expired),
    # redis sets the value to 0 before incrementing.
    value = client.incr(key)

    if (value % 1000000) == 0:
        # To prevent the numbers from growing indefinitely, we'll delete
        # the key once it reaches 1,000,000. If an error happens when we
        # try to delete, it will try it again at 2,000,000, and so on.
        client.delete(key)

    index = value % len(objects)
    return objects[index]
