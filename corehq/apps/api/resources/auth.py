import json
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseForbidden

from attrs import define, field
from tastypie.authentication import Authentication

from corehq.apps.api.odata.views import odata_permissions_check
from corehq.apps.domain.auth import BASIC, determine_authtype_from_header
from corehq.apps.domain.decorators import (
    api_key_auth,
    basic_auth_or_try_api_key_auth,
    get_auth_decorator_map,
)
from corehq.apps.users.decorators import (
    require_api_permission,
    require_permission_raw,
)
from corehq.toggles import IS_CONTRACTOR


def wrap_4xx_errors_for_apis(view_func):
    @wraps(view_func)
    def _inner(req, *args, **kwargs):
        try:
            return view_func(req, *args, **kwargs)
        except Http404 as e:
            if str(e):
                return HttpResponse(json.dumps({"error": str(e)}),
                                content_type="application/json",
                                status=404)
            return HttpResponse(json.dumps({"error": "not authorized"}),
                                content_type="application/json",
                                status=401)
    return _inner


@define
class ApiIdentifier:
    username = field()
    domain = field()


def get_rate_limit_identifier(request):
    couch_user = getattr(request, 'couch_user', None)
    if couch_user is not None:
        username = couch_user.username
    else:
        username = ''
    domain = getattr(request, 'domain', '')
    return ApiIdentifier(username=username, domain=domain)


class HQAuthenticationMixin:
    decorator_map = {}  # should be set by subclasses

    def _get_auth_decorator(self, request):
        return self.decorator_map[determine_authtype_from_header(request)]

    def get_identifier(self, request):
        return get_rate_limit_identifier(request)


class SSOAuthentication(HQAuthenticationMixin, Authentication):
    pass


class LoginAuthentication(HQAuthenticationMixin, Authentication):
    """
    Just checks you are able to login. Does not check against any permissions/domains, etc.
    """
    def __init__(self, allow_session_auth=False):
        super().__init__()
        self.decorator_map = get_auth_decorator_map(require_domain=False, allow_sessions=allow_session_auth)

    def is_authenticated(self, request, **kwargs):
        return self._auth_test(request, wrappers=[
            self._get_auth_decorator(request),
            wrap_4xx_errors_for_apis,
        ], **kwargs)

    def _auth_test(self, request, wrappers, **kwargs):
        PASSED_AUTH = object()

        def dummy(request, **kwargs):
            return PASSED_AUTH

        wrapped_dummy = dummy
        for wrapper in wrappers:
            wrapped_dummy = wrapper(wrapped_dummy)

        try:
            response = wrapped_dummy(request, **kwargs)
            return response is PASSED_AUTH
        except PermissionDenied:
            return False


class LoginAndDomainAuthentication(HQAuthenticationMixin, Authentication):

    def __init__(self, allow_session_auth=False, *args, **kwargs):
        """
        allow_session_auth:
            set this to True to allow session based access to this resource
        """
        super(LoginAndDomainAuthentication, self).__init__(*args, **kwargs)
        self.decorator_map = get_auth_decorator_map(require_domain=True, allow_sessions=allow_session_auth)

    def is_authenticated(self, request, **kwargs):
        return self._auth_test(request, wrappers=[
            require_api_permission('access_api', login_decorator=self._get_auth_decorator(request)),
            wrap_4xx_errors_for_apis,
        ], **kwargs)

    def _auth_test(self, request, wrappers, **kwargs):
        PASSED_AUTH = 'is_authenticated'

        def dummy(request, domain, **kwargs):
            return PASSED_AUTH

        wrapped_dummy = dummy
        for wrapper in wrappers:
            wrapped_dummy = wrapper(wrapped_dummy)

        if 'domain' not in kwargs:
            kwargs['domain'] = request.domain

        try:
            response = wrapped_dummy(request, **kwargs)
        except PermissionDenied:
            response = HttpResponseForbidden()

        if response == PASSED_AUTH:
            return True
        else:
            return response


class NoAPIPermissionsAuthentication(LoginAndDomainAuthentication):
    """
    Checks for domain and login and does not check for access api permissions
    """
    def __init__(self, *args, **kwargs):
        super(NoAPIPermissionsAuthentication, self).__init__(*args, **kwargs)

    def is_authenticated(self, request, **kwargs):
        return self._auth_test(request, wrappers=[
            self._get_auth_decorator(request),
            wrap_4xx_errors_for_apis,
        ], **kwargs)


class RequirePermissionAuthentication(LoginAndDomainAuthentication):

    def __init__(self, permission, *args, **kwargs):
        super(RequirePermissionAuthentication, self).__init__(*args, **kwargs)
        self.permission = permission

    def is_authenticated(self, request, **kwargs):
        wrappers = [
            require_api_permission(self.permission, login_decorator=self._get_auth_decorator(request)),
            wrap_4xx_errors_for_apis,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class ODataAuthentication(LoginAndDomainAuthentication):

    def __init__(self, *args, **kwargs):
        super(ODataAuthentication, self).__init__(*args, **kwargs)
        self.decorator_map = {
            'basic': basic_auth_or_try_api_key_auth,
            'api_key': api_key_auth,
        }

    def is_authenticated(self, request, **kwargs):
        wrappers = [
            require_permission_raw(
                odata_permissions_check,
                self._get_auth_decorator(request)
            ),
            wrap_4xx_errors_for_apis,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)

    def _get_auth_decorator(self, request):
        return self.decorator_map[determine_authtype_from_header(request, default=BASIC)]


class DomainAdminAuthentication(LoginAndDomainAuthentication):

    def is_authenticated(self, request, **kwargs):
        permission_check = lambda couch_user, domain: couch_user.is_domain_admin(domain)
        wrappers = [
            require_permission_raw(permission_check, login_decorator=self._get_auth_decorator(request)),
            wrap_4xx_errors_for_apis,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class AdminAuthentication(LoginAndDomainAuthentication):

    @staticmethod
    def _permission_check(couch_user, domain):
        return (
            couch_user.is_superuser or IS_CONTRACTOR.enabled(couch_user.username)
        )

    def is_authenticated(self, request, **kwargs):
        decorator = require_permission_raw(
            self._permission_check,
            login_decorator=self._get_auth_decorator(request)
        )
        wrappers = [decorator, wrap_4xx_errors_for_apis]
        # passing the domain is a hack to work around non-domain-specific requests
        # failing on auth
        return self._auth_test(request, wrappers=wrappers, domain='dimagi', **kwargs)
