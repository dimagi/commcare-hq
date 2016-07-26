# Standard library imports
from functools import wraps
import json

# Django imports
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.auth import determine_authtype_from_header
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.conf import settings

# Tastypie imports
from tastypie.authentication import Authentication
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.throttle import CacheThrottle

# External imports
from corehq.apps.users.decorators import require_permission, require_permission_raw
from corehq.toggles import API_THROTTLE_WHITELIST

# CCHQ imports
from corehq.apps.domain.decorators import (
    digest_auth,
    basic_auth,
    api_key_auth,
    login_or_digest,
    login_or_basic,
    login_or_api_key,
    superuser_or_dev_digest_auth,
    superuser_or_dev_basic_auth,
    superuser_or_dev_apikey_auth)

# API imports
from .serializers import CustomXMLSerializer


def api_auth(view_func):
    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        try:
            return view_func(req, domain, *args, **kwargs)
        except Http404, ex:
            if ex.message:
                return HttpResponse(json.dumps({"error": ex.message}),
                                    content_type="application/json",
                                    status=404)
            return HttpResponse(json.dumps({"error": "not authorized"}),
                                content_type="application/json",
                                status=401)
    return _inner


def api_access_allowed(request):
    # Checks if request.user or request.domain has API access permission
    return (request.user.is_superuser or
            (hasattr(request, 'domain') and domain_has_privilege(request.domain, privileges.API_ACCESS)))


class LoginAndDomainAuthentication(Authentication):

    def __init__(self, allow_session_auth=False, *args, **kwargs):
        """
        This Authentication class is intended to be used on a domain-specific resource
        It authenticates user, validates domain and membership and validates API accessibility

        allow_session_auth:
            set this to True to allow session based access to the resource
        """
        super(LoginAndDomainAuthentication, self).__init__(*args, **kwargs)
        self.allow_session_auth = allow_session_auth

    @property
    def decorator_map(self):
        if self.allow_session_auth:
            decorator_map = {
                'digest': login_or_digest,
                'basic': login_or_basic,
                'api_key': login_or_api_key,
            }
        else:
            decorator_map = {
                'digest': digest_auth,
                'basic': basic_auth,
                'api_key': api_key_auth,
            }
        return decorator_map

    def is_authenticated(self, request, **kwargs):
        return self._auth_test(request, wrappers=[self._get_auth_decorator(request), api_auth], **kwargs)

    def _get_auth_decorator(self, request):
        # the initial digest request doesn't have any authorization, so default to
        # digest in order to send back
        return self.decorator_map[determine_authtype_from_header(request, default='digest')]

    def _auth_test(self, request, wrappers, **kwargs):
        PASSED_AUTH = 'is_authenticated'

        def dummy(request, domain=None, **kwargs):
            return PASSED_AUTH

        wrapped_dummy = dummy
        for wrapper in wrappers:
            wrapped_dummy = wrapper(wrapped_dummy)

        if 'domain' not in kwargs:
            kwargs['domain'] = getattr(request, 'domain', None)

        try:
            response = wrapped_dummy(request, **kwargs)
        except PermissionDenied:
            response = HttpResponseForbidden()

        if not api_access_allowed(request):
            response = HttpResponse(
                json.dumps({"error": "Your current plan does not have access to this feature"}),
                content_type="application/json",
                status=401
            )

        if response == PASSED_AUTH:
            return True
        else:
            return response

    def get_identifier(self, request):
        return request.couch_user.username


class RequirePermissionAuthentication(LoginAndDomainAuthentication):
    # Authentication class to check extra permission along with user authentication
    # and domain-check.
    def __init__(self, permission, *args, **kwargs):
        super(RequirePermissionAuthentication, self).__init__(*args, **kwargs)
        self.permission = permission

    def is_authenticated(self, request, **kwargs):
        wrappers = [
            require_permission(self.permission, login_decorator=self._get_auth_decorator(request)),
            api_auth,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class DomainAdminAuthentication(LoginAndDomainAuthentication):
    # Authentication class to check that user is domain admin along with user authentication
    def is_authenticated(self, request, **kwargs):
        permission_check = lambda couch_user, domain: couch_user.is_domain_admin(domain)
        wrappers = [
            require_permission_raw(permission_check, login_decorator=self._get_auth_decorator(request)),
            api_auth,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class AdminAuthentication(LoginAndDomainAuthentication):
    # Authentication class to check superuser permission
    # This does not validate user-domain relationship, it is intended to be used in admin resources
    @property
    def decorator_map(self):
        # superuser decorators that authenticate user and check superuser permissions
        return {
            'digest': superuser_or_dev_digest_auth,
            'basic': superuser_or_dev_basic_auth,
            'api_key': superuser_or_dev_apikey_auth,
        }

    def is_authenticated(self, request, **kwargs):
        decorator = self._get_auth_decorator(request)
        wrappers = [decorator]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class HQThrottle(CacheThrottle):

    def should_be_throttled(self, identifier, **kwargs):
        if API_THROTTLE_WHITELIST.enabled(identifier):
            return False

        return super(HQThrottle, self).should_be_throttled(identifier, **kwargs)


class CustomResourceMeta(object):
    authorization = ReadOnlyAuthorization()
    authentication = LoginAndDomainAuthentication()
    serializer = CustomXMLSerializer()
    default_format = 'application/json'
    throttle = HQThrottle(throttle_at=getattr(settings, 'CCHQ_API_THROTTLE_REQUESTS', 25),
                          timeframe=getattr(settings, 'CCHQ_API_THROTTLE_TIMEFRAME', 15))
