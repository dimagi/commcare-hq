# Standard Library imports
from __future__ import absolute_import
from __future__ import unicode_literals
from functools import wraps
import logging

import six

# Django imports
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.urls import reverse
from django.http import (
    HttpResponse, HttpResponseRedirect, Http404, HttpResponseForbidden, JsonResponse, HttpRequest,
)
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator, available_attrs
from django.utils.http import urlquote
from django.utils.translation import ugettext as _
from django.views import View

# External imports
from dimagi.utils.django.request import mutable_querydict
from django_digest.decorators import httpdigest
from corehq.apps.domain.auth import (
    determine_authtype_from_request, basicauth,
    BASIC, DIGEST, API_KEY,
    get_username_and_password_from_request, FORMPLAYER,
    formplayer_auth, formplayer_as_user_auth, basic_or_api_key)

from tastypie.authentication import ApiKeyAuthentication
from tastypie.http import HttpUnauthorized
from dimagi.utils.web import json_response

from django_otp import match_token

# CCHQ imports
from corehq.apps.domain.models import Domain, DomainAuditRecordEntry
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.users.models import CouchUser
from corehq.apps.hqwebapp.signals import clear_login_attempts
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.soft_assert import soft_assert

########################################################################################################
from corehq.toggles import IS_CONTRACTOR, DATA_MIGRATION, PUBLISH_CUSTOM_REPORTS, TWO_FACTOR_SUPERUSER_ROLLOUT


logger = logging.getLogger(__name__)

REDIRECT_FIELD_NAME = 'next'

OTP_AUTH_FAIL_RESPONSE = {"error": "must send X-COMMCAREHQ-OTP header or 'otp' URL parameter"}


def load_domain(req, domain):
    domain_name = normalize_domain_name(domain)
    domain_obj = Domain.get_by_name(domain_name)
    req.project = domain_obj
    return domain_name, domain_obj

########################################################################################################


def redirect_for_login_or_domain(request, login_url=None):
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(request.get_full_path(), login_url)


def _page_is_whitelist(path, domain):
    pages_not_restricted_for_dimagi = getattr(settings, "PAGES_NOT_RESTRICTED_FOR_DIMAGI", tuple())
    return bool([
        x for x in pages_not_restricted_for_dimagi if x % {'domain': domain} == path
    ])


def login_and_domain_required(view_func):

    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        user = req.user
        domain_name, domain = load_domain(req, domain)
        if not domain:
            msg = _('The domain "{domain}" was not found.').format(domain=domain_name)
            raise Http404(msg)

        if user.is_authenticated and user.is_active:
            if not domain.is_active:
                msg = _(
                    'The project space "{domain}" has not yet been activated. '
                    'Please report an issue if you think this is a mistake.'
                ).format(domain=domain_name)
                messages.info(req, msg)
                return HttpResponseRedirect(reverse("domain_select"))
            couch_user = _ensure_request_couch_user(req)
            if couch_user.is_member_of(domain):
                # If the two factor toggle is on, require it for all users.
                if (
                    _two_factor_required(view_func, domain, couch_user)
                    and not getattr(req, 'bypass_two_factor', False)
                    and not user.is_verified()
                ):
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
            elif couch_user.is_web_user() and domain.allow_domain_requests:
                from corehq.apps.users.views import DomainRequestView
                return DomainRequestView.as_view()(req, *args, **kwargs)
            else:
                raise Http404
        elif (
            req.path.startswith('/a/{}/reports/custom'.format(domain_name)) and
            PUBLISH_CUSTOM_REPORTS.enabled(domain_name)
        ):
            return view_func(req, domain_name, *args, **kwargs)
        else:
            login_url = reverse('domain_login', kwargs={'domain': domain_name})
            return redirect_for_login_or_domain(req, login_url=login_url)

    return _inner


def _ensure_request_couch_user(request):
    couch_user = getattr(request, 'couch_user', None)
    if not couch_user and hasattr(request, 'user'):
        request.couch_user = couch_user = CouchUser.from_django_user(request.user)
    return couch_user


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
                @two_factor_check(fn, api_key)
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


def login_or_basic_or_api_key_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(basic_or_api_key(), allow_cc_users=allow_cc_users, allow_sessions=allow_sessions)


def login_or_digest_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(httpdigest, allow_cc_users=allow_cc_users, allow_sessions=allow_sessions)


def login_or_formplayer_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(
        formplayer_as_user_auth,
        allow_cc_users=allow_cc_users, allow_sessions=allow_sessions
    )


def login_or_api_key_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(
        api_key(),
        allow_cc_users=allow_cc_users,
        api_key=True,
        allow_sessions=allow_sessions
    )


def _get_multi_auth_decorator(default, allow_formplayer=False):
    """
    :param allow_formplayer: If True this will allow one additional auth mechanism which is used
         by Formplayer:

         - formplayer auth: for SMS forms there is no active user involved in the session and so
             formplayer can not use the session cookie to auth. To allow formplayer access to the
             endpoints we validate each formplayer request using a shared key. See the auth
             function for more details.
    """
    def decorator(fn):
        @wraps(fn)
        def _inner(request, *args, **kwargs):
            authtype = determine_authtype_from_request(request, default=default)
            if authtype == FORMPLAYER and not allow_formplayer:
                return HttpResponseForbidden()
            function_wrapper = {
                BASIC: login_or_basic_ex(allow_cc_users=True),
                DIGEST: login_or_digest_ex(allow_cc_users=True),
                API_KEY: login_or_api_key_ex(allow_cc_users=True),
                FORMPLAYER: login_or_formplayer_ex(allow_cc_users=True),
            }[authtype]
            return function_wrapper(fn)(request, *args, **kwargs)
        return _inner
    return decorator


def two_factor_exempt(view_func):
    """
    Marks a view function as being exempt from two factor authentication.
    """
    # We could just do view_func.two_factor_exempt = True, but decorators
    # are nicer if they don't have side-effects, so we return a new
    # function.
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)
    wrapped_view.two_factor_exempt = True
    return wraps(view_func, assigned=available_attrs(view_func))(wrapped_view)


# This decorator should be used for any endpoints used by CommCare mobile
# It supports basic, session, and apikey auth, but not digest
# Endpoints with this decorator will not enforce two factor authentication
def mobile_auth(view_func):
    return _get_multi_auth_decorator(default=BASIC)(two_factor_exempt(view_func))


# This decorator is used only for anonymous web apps and SMS forms
# Endpoints with this decorator will not enforce two factor authentication
def mobile_auth_or_formplayer(view_func):
    return _get_multi_auth_decorator(default=BASIC, allow_formplayer=True)(two_factor_exempt(view_func))


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

basic_auth_or_try_api_key_auth = login_or_basic_or_api_key_ex(allow_sessions=False)


def two_factor_check(view_func, api_key):
    def _outer(fn):
        @wraps(fn)
        def _inner(request, domain, *args, **kwargs):
            domain_obj = Domain.get_by_name(domain)
            couch_user = _ensure_request_couch_user(request)
            if (
                not api_key and
                not getattr(request, 'skip_two_factor_check', False) and
                domain_obj and
                _two_factor_required(view_func, domain_obj, couch_user)
            ):
                token = request.META.get('HTTP_X_COMMCAREHQ_OTP')
                if not token and 'otp' in request.GET:
                    with mutable_querydict(request.GET):
                        # remove the param from the query dict so that we don't interfere with places
                        # that use the query dict to generate dynamic filters
                        token = request.GET.pop('otp')[-1]
                if not token:
                    return JsonResponse(OTP_AUTH_FAIL_RESPONSE, status=401)
                otp_device = match_token(request.user, token)
                if not otp_device:
                    return JsonResponse({"error": "OTP token is incorrect"}, status=401)

                # set otp device and is_verified function on user to be consistent with OTP middleware
                request.user.otp_device = otp_device
                request.user.is_verified = lambda: True
                return fn(request, domain, *args, **kwargs)
            return fn(request, domain, *args, **kwargs)
        return _inner
    return _outer


def _two_factor_required(view_func, domain, couch_user):
    exempt = getattr(view_func, 'two_factor_exempt', False)
    if exempt:
        return False
    return (
        (domain.two_factor_auth or TWO_FACTOR_SUPERUSER_ROLLOUT.enabled(couch_user.username))
        and not couch_user.two_factor_disabled
    )


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

    Currently only required by for a single view used by 'kawok-vc-desarrollo' domain
    See http://manage.dimagi.com/default.asp?225116#1137527
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
        user = request.user
        if not (user.is_authenticated and user.is_active):
            return redirect_for_login_or_domain(request)

        # User's login and domain have been validated - it's safe to call the view function
        return view_func(request, *args, **kwargs)
    return _inner


def check_lockout(fn):
    @wraps(fn)
    def _inner(request, *args, **kwargs):
        username, password = get_username_and_password_from_request(request)
        if not username:
            return fn(request, *args, **kwargs)

        user = CouchUser.get_by_username(username)
        if user and user.is_locked_out() and user.supports_lockout():
            return json_response({"error": _("maximum password attempts exceeded")}, status_code=401)
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


def require_superuser_or_contractor(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        user = request.user
        if IS_CONTRACTOR.enabled(user.username) or user.is_superuser:
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

cls_require_superuser_or_contractor = cls_to_view(additional_decorator=require_superuser_or_contractor)


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


def track_domain_request(calculated_prop):
    """
    Use this decorator to audit requests by domain.
    """
    norman = ''.join(reversed('moc.igamid@repoohn'))
    _soft_assert = soft_assert(to=norman)

    def _dec(view_func):

        @wraps(view_func)
        def _wrapped(*args, **kwargs):
            if 'domain' in kwargs:
                domain = kwargs['domain']
            elif (
                    len(args) > 2 and
                    isinstance(args[0], View) and
                    isinstance(args[1], HttpRequest) and
                    isinstance(args[2], six.string_types)
            ):
                soft_assert_type_text(args[2])
                # class-based view; args == (self, request, domain, ...)
                domain = args[2]
            elif (
                    len(args) > 1 and
                    isinstance(args[0], HttpRequest) and
                    isinstance(args[1], six.string_types)
            ):
                soft_assert_type_text(args[1])
                # view function; args == (request, domain, ...)
                domain = args[1]
            else:
                domain = None
            if _soft_assert(
                    domain,
                    'Unable to track_domain_request("{prop}") on view "{view}". Unable to determine domain from '
                    'args {args}.'.format(prop=calculated_prop, view=view_func.__name__, args=args)
            ):
                DomainAuditRecordEntry.update_calculations(domain, calculated_prop)
            return view_func(*args, **kwargs)

        return _wrapped

    return _dec
