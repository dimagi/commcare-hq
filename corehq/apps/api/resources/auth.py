from __future__ import absolute_import
from __future__ import unicode_literals
import json
from functools import wraps

import six
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseForbidden
from tastypie.authentication import Authentication

from corehq.apps.domain.auth import determine_authtype_from_header, BASIC
from corehq.apps.domain.decorators import (
    digest_auth,
    basic_auth,
    api_key_auth,
    basic_auth_or_try_api_key_auth,
    login_or_digest,
    login_or_basic,
    login_or_api_key)
from corehq.apps.users.decorators import require_permission, require_permission_raw
from corehq.toggles import IS_CONTRACTOR


def api_auth(view_func):
    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        try:
            return view_func(req, domain, *args, **kwargs)
        except Http404 as e:
            if six.text_type(e):
                return HttpResponse(json.dumps({"error": six.text_type(e)}),
                                content_type="application/json",
                                status=404)
            return HttpResponse(json.dumps({"error": "not authorized"}),
                                content_type="application/json",
                                status=401)
    return _inner


class LoginAndDomainAuthentication(Authentication):

    def __init__(self, allow_session_auth=False, *args, **kwargs):
        """
        allow_session_auth:
            set this to True to allow session based access to this resource
        """
        super(LoginAndDomainAuthentication, self).__init__(*args, **kwargs)
        if allow_session_auth:
            self.decorator_map = {
                'digest': login_or_digest,
                'basic': login_or_basic,
                'api_key': login_or_api_key,
            }
        else:
            self.decorator_map = {
                'digest': digest_auth,
                'basic': basic_auth,
                'api_key': api_key_auth,
            }

    def is_authenticated(self, request, **kwargs):
        return self._auth_test(request, wrappers=[self._get_auth_decorator(request), api_auth], **kwargs)

    def _get_auth_decorator(self, request):
        # the initial digest request doesn't have any authorization, so default to
        # digest in order to send back
        return self.decorator_map[determine_authtype_from_header(request)]

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

    def get_identifier(self, request):
        return request.couch_user.username


class RequirePermissionAuthentication(LoginAndDomainAuthentication):

    def __init__(self, permission, *args, **kwargs):
        super(RequirePermissionAuthentication, self).__init__(*args, **kwargs)
        self.permission = permission

    def is_authenticated(self, request, **kwargs):
        wrappers = [
            require_permission(self.permission, login_decorator=self._get_auth_decorator(request)),
            api_auth,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class ODataAuthentication(RequirePermissionAuthentication):

    def __init__(self, *args, **kwargs):
        super(ODataAuthentication, self).__init__(*args, **kwargs)
        self.decorator_map = {
            'basic': basic_auth_or_try_api_key_auth,
            'api_key': api_key_auth,
        }

    def _get_auth_decorator(self, request):
        return self.decorator_map[determine_authtype_from_header(request, default=BASIC)]


class DomainAdminAuthentication(LoginAndDomainAuthentication):

    def is_authenticated(self, request, **kwargs):
        permission_check = lambda couch_user, domain: couch_user.is_domain_admin(domain)
        wrappers = [
            require_permission_raw(permission_check, login_decorator=self._get_auth_decorator(request)),
            api_auth,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class AdminAuthentication(LoginAndDomainAuthentication):

    @staticmethod
    def _permission_check(couch_user, domain):
        return (
            couch_user.is_superuser or
            IS_CONTRACTOR.enabled(couch_user.username)
        )

    def is_authenticated(self, request, **kwargs):
        decorator = require_permission_raw(
            self._permission_check,
            login_decorator=self._get_auth_decorator(request)
        )
        wrappers = [decorator, api_auth]
        # passing the domain is a hack to work around non-domain-specific requests
        # failing on auth
        return self._auth_test(request, wrappers=wrappers, domain='dimagi', **kwargs)
