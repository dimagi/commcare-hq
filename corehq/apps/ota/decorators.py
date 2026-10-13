import logging
from functools import wraps

from django.http import HttpResponseForbidden

from corehq.apps.domain.auth import BASIC
from corehq.apps.domain.decorators import (
    get_multi_auth_decorator,
    two_factor_exempt,
)
from corehq.apps.ota.origin_token import (
    ORIGIN_TOKEN_HEADER,
    is_from_formplayer,
    validate_origin_token,
)
from corehq.apps.public_webforms.decorators import get_public_form_session
from corehq.apps.public_webforms.models import PublicFormUser
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions

auth_logger = logging.getLogger("commcare_auth")


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


def mobile_auth_or_public_form_session(view_func):
    """
    Accepts a public form session alongside the usual mobile credentials.
    """
    @wraps(view_func)
    def _inner(request, domain, *args, **kwargs):
        session = get_public_form_session(request, domain)
        if session is None:
            return mobile_auth_or_formplayer(view_func)(request, domain, *args, **kwargs)
        if not is_from_formplayer(request):
            return HttpResponseForbidden()

        request.public_form_session = session
        request.couch_user = PublicFormUser(session)
        return view_func(request, domain, *args, **kwargs)

    return _inner
