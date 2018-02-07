# Standard Library imports
from __future__ import absolute_import
from functools import wraps
import logging
from base64 import b64decode

# Django imports
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.urls import reverse
from django.http import (
    HttpResponse, HttpResponseRedirect, Http404, HttpResponseForbidden, JsonResponse,
)
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.http import urlquote
from django.utils.translation import ugettext as _

# External imports
from django_digest.decorators import httpdigest
from corehq.apps.domain.auth import (
    determine_authtype_from_request, basicauth, tokenauth,
    BASIC, DIGEST, API_KEY, TOKEN,
    get_username_and_password_from_request)
from python_digest import parse_digest_credentials

from tastypie.authentication import ApiKeyAuthentication
from tastypie.http import HttpUnauthorized
from dimagi.utils.web import json_response

from django_otp import match_token

# CCHQ imports
from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.users.models import CouchUser
from corehq.apps.hqwebapp.signals import clear_login_attempts

########################################################################################################
from corehq.toggles import IS_DEVELOPER, DATA_MIGRATION, PUBLISH_CUSTOM_REPORTS

logger = logging.getLogger(__name__)

REDIRECT_FIELD_NAME = 'next'


def load_domain(req, domain):
    domain_name = normalize_domain_name(domain)
    domain = Domain.get_by_name(domain_name)
    req.project = domain
    return domain_name, domain

########################################################################################################


def _redirect_for_login_or_domain(request, redirect_field_name, login_url):
    path = urlquote(request.get_full_path())
    nextURL = '%s?%s=%s' % (login_url, redirect_field_name, path)
    return HttpResponseRedirect(nextURL)


def _page_is_whitelist(path, domain):
    pages_not_restricted_for_dimagi = getattr(settings, "PAGES_NOT_RESTRICTED_FOR_DIMAGI", tuple())
    return bool([
        x for x in pages_not_restricted_for_dimagi if x % {'domain': domain} == path
    ])


def domain_specific_login_redirect(request, domain):
    project = Domain.get_by_name(domain)
    login_url = reverse('login')
    return _redirect_for_login_or_domain(request, 'next', login_url)


def login_and_domain_required(view_func):

    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        user = req.user
        domain_name, domain = load_domain(req, domain)
        if not domain:
            msg = _(('The domain "{domain}" was not found.').format(domain=domain_name))
            raise Http404(msg)

        if user.is_authenticated and user.is_active:
            if not domain.is_active:
                msg = _((
                    'The domain "{domain}" has not yet been activated. '
                    'Please report an issue if you think this is a mistake.'
                ).format(domain=domain_name))
                messages.info(req, msg)
                return HttpResponseRedirect(reverse("domain_select"))
            couch_user = _ensure_request_couch_user(req)
            if couch_user.is_member_of(domain):
                if (_two_factor_required(domain, couch_user) and not user.is_verified()):
                    return TemplateResponse(
                        request=req,
                        template='two_factor/core/otp_required.html',
                        status=403,
                    )
                else:
                    return view_func(req, domain_name, *args, **kwargs)

            elif (
                _page_is_whitelist(req.path, domain_name) or
                not domain.restrict_superusers
            ) and user.is_superuser:
                # superusers can circumvent domain permissions.
                return view_func(req, domain_name, *args, **kwargs)
            elif domain.is_snapshot:
                # snapshots are publicly viewable
                return require_previewer(view_func)(req, domain_name, *args, **kwargs)
            elif domain.allow_domain_requests:
                from corehq.apps.users.views import DomainRequestView
                return DomainRequestView.as_view()(req, *args, **kwargs)
            else:
                raise Http404
        elif (
            req.path.startswith(u'/a/{}/reports/custom'.format(domain_name)) and
            PUBLISH_CUSTOM_REPORTS.enabled(domain_name)
        ):
            return view_func(req, domain_name, *args, **kwargs)
        else:
            login_url = reverse('domain_login', kwargs={'domain': domain})
            return _redirect_for_login_or_domain(req, REDIRECT_FIELD_NAME, login_url)


    return _inner


def _ensure_request_couch_user(request):
    couch_user = getattr(request, 'couch_user', None)
    if not couch_user and hasattr(request, 'user'):
        request.couch_user = couch_user = CouchUser.from_django_user(request.user)
    return couch_user


def domain_required(view_func):
    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        domain_name, domain = load_domain(req, domain)
        if domain:
            return view_func(req, domain_name, *args, **kwargs)
        else:
            msg = _(('The domain "{domain}" was not found.').format(domain=domain_name))
            raise Http404(msg)
    return _inner


class LoginAndDomainMixin(object):

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)


def api_key():
    api_auth_class = ApiKeyAuthentication()

    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            auth = api_auth_class.is_authenticated(request)
            if auth:
                if isinstance(auth, HttpUnauthorized):
                    return auth
                return view(request, *args, **kwargs)

            response = HttpUnauthorized()
            return response
        return wrapper
    return real_decorator


def _login_or_challenge(challenge_fn, allow_cc_users=False, api_key=False, allow_sessions=True):
    """
    kwargs:
        allow_cc_users: authorize non-WebUser users
        allow_sessions: allow session based authorization
    """
    # ensure someone is logged in, or challenge
    # challenge_fn should itself be a decorator that can handle authentication
    def _outer(fn):
        @wraps(fn)
        def safe_fn(request, domain, *args, **kwargs):
            if request.user.is_authenticated and allow_sessions:
                return login_and_domain_required(fn)(request, domain, *args, **kwargs)
            else:
                # if sessions are blocked or user is not already authenticated, check for authentication
                @check_lockout
                @challenge_fn
                @two_factor_check(api_key)
                def _inner(request, domain, *args, **kwargs):
                    couch_user = _ensure_request_couch_user(request)
                    if (
                        couch_user
                        and (allow_cc_users or couch_user.is_web_user())
                        and couch_user.is_member_of(domain)
                    ):
                        clear_login_attempts(couch_user)
                        return fn(request, domain, *args, **kwargs)
                    else:
                        return HttpResponseForbidden()

                return _inner(request, domain, *args, **kwargs)
        return safe_fn
    return _outer


def login_or_basic_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(basicauth(), allow_cc_users=allow_cc_users, allow_sessions=allow_sessions)


def login_or_digest_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(httpdigest, allow_cc_users=allow_cc_users, allow_sessions=allow_sessions)


def login_or_token_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(tokenauth, allow_cc_users=allow_cc_users, allow_sessions=allow_sessions)


def login_or_api_key_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(
        api_key(),
        allow_cc_users=allow_cc_users,
        api_key=True,
        allow_sessions=allow_sessions
    )


def _get_multi_auth_decorator(default, allow_token=False, allow_two_factor=True):
    def decorator(fn):
        @wraps(fn)
        def _inner(request, *args, **kwargs):
            authtype = determine_authtype_from_request(request, default=default)
            if authtype == TOKEN and not allow_token:
                return HttpResponseForbidden()
            function_wrapper = {
                BASIC: login_or_basic_ex(allow_cc_users=True),
                DIGEST: login_or_digest_ex(allow_cc_users=True),
                API_KEY: login_or_api_key_ex(allow_cc_users=True),
                TOKEN: login_or_token_ex(allow_cc_users=True),
            }[authtype]
            return function_wrapper(fn)(request, *args, **kwargs)
        return _inner
    return decorator


# This decorator should be used for any endpoints used by CommCare mobile
# It supports basic, session, and apikey auth, but not digest
mobile_auth = _get_multi_auth_decorator(default=BASIC)

# This decorator is deprecated, it's used only for anonymous web apps
mobile_auth_or_token = _get_multi_auth_decorator(
    default=BASIC, allow_token=True)

# Use this decorator to allow any auth type -
# basic, digest, session, or apikey
api_auth = _get_multi_auth_decorator(default=DIGEST)

# Use these decorators on views to allow sesson-auth or an extra authorization method
login_or_digest = login_or_digest_ex()
login_or_basic = login_or_basic_ex()
login_or_api_key = login_or_api_key_ex()

# Use these decorators on views to exclusively allow any one authorization method and not session based auth
digest_auth = login_or_digest_ex(allow_sessions=False)
basic_auth = login_or_basic_ex(allow_sessions=False)
api_key_auth = login_or_api_key_ex(allow_sessions=False)


def two_factor_check(api_key):
    def _outer(fn):
        @wraps(fn)
        def _inner(request, domain, *args, **kwargs):
            dom = Domain.get_by_name(domain)
            couch_user = _ensure_request_couch_user(request)
            if not api_key and dom and _two_factor_required(dom, couch_user):
                token = request.META.get('HTTP_X_COMMCAREHQ_OTP')
                if token and match_token(request.user, token):
                    return fn(request, *args, **kwargs)
                else:
                    return JsonResponse({"error": "must send X-CommcareHQ-OTP header"}, status=401)
            return fn(request, domain, *args, **kwargs)
        return _inner
    return _outer


def _two_factor_required(domain, couch_user):
    return domain.two_factor_auth and couch_user.is_web_user() and not couch_user.two_factor_disabled


def cls_to_view(additional_decorator=None):
    def decorator(func):
        def __outer__(cls, request, *args, **kwargs):
            domain = kwargs.get('domain')
            new_kwargs = kwargs.copy()
            if not domain:
                try:
                    domain = args[0]
                except IndexError:
                    pass
            else:
                del new_kwargs['domain']

            def __inner__(request, domain, *args, **new_kwargs):
                return func(cls, request, *args, **kwargs)

            if additional_decorator:
                return additional_decorator(__inner__)(request, domain, *args, **new_kwargs)
            else:
                return __inner__(request, domain, *args, **new_kwargs)
        return __outer__
    return decorator


def api_domain_view(view):
    """
    Decorate this with any domain view that should be accessed via api only
    """
    @wraps(view)
    @api_key()
    @login_and_domain_required
    def _inner(request, domain, *args, **kwargs):
        if request.user.is_authenticated:
            _ensure_request_couch_user(request)
            return view(request, domain, *args, **kwargs)
        else:
            return HttpResponseForbidden()
    return _inner


def login_required(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        login_url = reverse('login')
        user = request.user
        if not (user.is_authenticated and user.is_active):
            return _redirect_for_login_or_domain(request,
                    REDIRECT_FIELD_NAME, login_url)

        # User's login and domain have been validated - it's safe to call the view function
        return view_func(request, *args, **kwargs)
    return _inner


def check_lockout(fn):
    @wraps(fn)
    def _inner(request, *args, **kwargs):
        username, password = get_username_and_password_from_request(request)
        if not username or username.endswith('.commcarehq.org'):
            return fn(request, *args, **kwargs)

        user = CouchUser.get_by_username(username)
        if user and (user.is_web_user() or toggles.MOBILE_LOGIN_LOCKOUT.enabled(user.domain)) and user.is_locked_out():
            return json_response({_("error"): _("maximum password attempts exceeded")}, status_code=401)
        else:
            return fn(request, *args, **kwargs)
    return _inner


########################################################################################################
#
# Have to write this to be sure this decorator still works if DOMAIN_NOT_ADMIN_REDIRECT_PAGE_NAME
# is not defined - people may forget to do this, because it's not a standard, defined Django
# config setting


def domain_admin_required_ex(redirect_page_name=None):
    # todo: this is weirdly similar but different to require_permission. they should probably be combined
    if redirect_page_name is None:
        redirect_page_name = getattr(settings, 'DOMAIN_NOT_ADMIN_REDIRECT_PAGE_NAME', 'homepage')

    def _outer(view_func):
        @login_and_domain_required
        @wraps(view_func)
        def _inner(request, domain, *args, **kwargs):
            if not hasattr(request, 'couch_user'):
                raise Http404()
            if not request.couch_user.is_web_user():
                raise Http404()
            domain_name, domain = load_domain(request, domain)
            if not domain:
                raise Http404()

            if not (
                _page_is_whitelist(request.path, domain_name) and request.user.is_superuser
            ) and not request.couch_user.is_domain_admin(domain_name):
                return HttpResponseRedirect(reverse(redirect_page_name))
            return view_func(request, domain_name, *args, **kwargs)

        return _inner
    return _outer


def require_superuser_or_developer(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        user = request.user
        if IS_DEVELOPER.enabled(user.username) or user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(reverse("no_permissions"))

    return _inner


# Parallel to what we did with login_and_domain_required, above
domain_admin_required = domain_admin_required_ex()
cls_domain_admin_required = cls_to_view(additional_decorator=domain_admin_required)

########################################################################################################
# couldn't figure how to call reverse, so login_url is the actual url
require_superuser = permission_required("is_superuser", login_url='/no_permissions/')
cls_require_superusers = cls_to_view(additional_decorator=require_superuser)

cls_require_superuser_or_developer = cls_to_view(additional_decorator=require_superuser_or_developer)


def require_previewer(view_func):
    def shim(request, *args, **kwargs):
        if not hasattr(request, 'couch_user') or not request.couch_user.is_previewer():
            raise Http404
        else:
            return view_func(request, *args, **kwargs)
    return shim

cls_require_previewer = cls_to_view(additional_decorator=require_previewer)


def check_domain_migration(view_func):
    def wrapped_view(request, domain, *args, **kwargs):
        if DATA_MIGRATION.enabled(domain):
            return HttpResponse('Service Temporarily Unavailable',
                                content_type='text/plain', status=503)
        return view_func(request, domain, *args, **kwargs)

    wrapped_view.domain_migration_handled = True
    return wraps(view_func)(wrapped_view)
