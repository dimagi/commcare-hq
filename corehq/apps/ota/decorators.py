import logging
from functools import wraps

from django.http import HttpResponseForbidden

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.domain.auth import BASIC
from corehq.apps.domain.decorators import (
    get_multi_auth_decorator,
    two_factor_exempt,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions

auth_logger = logging.getLogger("commcare_auth")

ORIGIN_TOKEN_HEADER = 'HTTP_X_COMMCAREHQ_ORIGIN_TOKEN'
ORIGIN_TOKEN_SLUG = 'OriginToken'


def require_mobile_access(fn):
    """
    This decorator restricts a view to users with the `access_mobile_endpoints`
    permission.
    It does not perform any authentication, which must be left to other
    decorators on the view.
    """
    @wraps(fn)
    def _inner(request, domain, *args, **kwargs):
        origin_token = request.META.get(ORIGIN_TOKEN_HEADER, None)
        if origin_token:
            if validate_origin_token(origin_token):
                return fn(request, domain, *args, **kwargs)
            else:
                auth_logger.info(
                    "Request rejected domain=%s reason=%s request=%s",
                    domain, "flag:mobile_access_restricted", request.path
                )
                return HttpResponseForbidden()

        return require_permission(
            HqPermissions.access_mobile_endpoints,
            login_decorator=None
        )(fn)(request, domain, *args, **kwargs)

    return _inner


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


def mobile_auth(view_func):
    """
    This decorator should be used for any endpoints used by CommCare mobile.
    It supports basic, session, and apikey auth, but not digest.
    Endpoints with this decorator will not enforce two factor authentication.
    """
    return get_multi_auth_decorator(default=BASIC, oauth_scopes=['sync'])(
        two_factor_exempt(
            require_mobile_access(view_func)
        )
    )


def mobile_auth_or_formplayer(view_func):
    """
    This decorator is used only for anonymous web apps and SMS forms.
    Endpoints with this decorator will not enforce two factor authentication.
    """
    return get_multi_auth_decorator(default=BASIC, allow_formplayer=True, oauth_scopes=['sync'])(
        two_factor_exempt(
            require_mobile_access(view_func)
        )
    )
