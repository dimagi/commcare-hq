from dimagi.utils.couch.cache.cache_core import get_redis_client

ORIGIN_TOKEN_HEADER = 'HTTP_X_COMMCAREHQ_ORIGIN_TOKEN'
ORIGIN_TOKEN_SLUG = 'OriginToken'


def is_from_formplayer(request):
    token = request.META.get(ORIGIN_TOKEN_HEADER)
    return token is not None and validate_origin_token(token)


def validate_origin_token(origin_token):
    """
    This checks that the origin token passed in is a valid one set in redis
    by Formplayer.
    """
    client = get_redis_client().client.get_client()
    test_result = client.get("%s%s" % (ORIGIN_TOKEN_SLUG, origin_token))
    if test_result:
        return test_result.decode("UTF-8") == '"valid"'

    return False
