from corehq import toggles
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions

from dimagi.utils.couch.cache.cache_core import get_redis_client

from functools import wraps

from django.http import HttpResponseForbidden

ORIGIN_TOKEN_HEADER = 'HTTP_X_COMMCAREHQ_ORIGIN_TOKEN'
ORIGIN_TOKEN_SLUG = 'OriginToken'


def require_mobile_access(fn):
    @wraps(fn)
    def _inner(request, domain, *args, **kwargs):
        if toggles.RESTRICT_MOBILE_ACCESS.enabled(domain):
            origin_token = request.META.get(ORIGIN_TOKEN_HEADER, None)
            if origin_token:
                if _test_token_valid(origin_token):
                    return fn(request, domain, *args, **kwargs)
                else:
                    return HttpResponseForbidden()

            return require_permission(Permissions.access_mobile_endpoints)(fn)(request, domain, *args, **kwargs)

        return fn(request, domain, *args, **kwargs)

    return _inner


def _test_token_valid(origin_token):
    client = get_redis_client().client.get_client()
    test_result = client.get("%s%s" % (ORIGIN_TOKEN_SLUG, origin_token))
    if test_result:
        return test_result.decode("UTF-8") == '"valid"'

    return False
