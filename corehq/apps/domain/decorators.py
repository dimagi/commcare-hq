import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View

from django_otp import match_token
from django_prbac.utils import has_privilege
from oauth2_provider.oauth2_backends import get_oauthlib_core
from tastypie.http import HttpUnauthorized

from dimagi.utils.django.request import mutable_querydict
from dimagi.utils.web import json_response

from corehq import privileges
from corehq.apps.domain.auth import (
    API_KEY,
    BASIC,
    DIGEST,
    FORMPLAYER,
    OAUTH2,
    HQApiKeyAuthentication,
    basic_or_api_key,
    basicauth,
    determine_authtype_from_request,
    formplayer_as_user_auth,
    get_username_and_password_from_request,
)
from corehq.apps.domain.models import Domain, DomainAuditRecordEntry
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.hqwebapp.signals import clear_login_attempts
from corehq.apps.sso.utils.request_helpers import (
    is_request_blocked_from_viewing_domain_due_to_sso,
    is_request_using_sso,
)
from corehq.apps.sso.utils.view_helpers import (
    render_untrusted_identity_provider_for_domain_view,
)
from corehq.apps.users.models import CouchUser
from corehq.toggles import (
    DATA_MIGRATION,
    IS_CONTRACTOR,
    TWO_FACTOR_SUPERUSER_ROLLOUT,
)
from corehq.util.soft_assert import soft_assert
from django_digest.decorators import httpdigest

auth_logger = logging.getLogger("commcare_auth")

OTP_AUTH_FAIL_RESPONSE = {"error": "must send X-COMMCAREHQ-OTP header or 'otp' URL parameter"}


def load_domain(req, domain):
    domain_name = normalize_domain_name(domain)
    _store_project_on_request(req, domain_name)
    return domain_name, req.project


def _store_project_on_request(request, domain_name):
    domain_obj = Domain.get_by_name(domain_name)
    request.project = domain_obj


def redirect_for_login_or_domain(request, login_url=None):
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(request.get_full_path(), login_url)


def login_and_domain_required(view_func):

    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        user = req.user
        domain_name, domain_obj = load_domain(req, domain)
        def call_view(): return view_func(req, domain_name, *args, **kwargs)
        if not domain_obj:
            msg = _('The domain "{domain}" was not found.').format(domain=domain_name)
            raise Http404(msg)

        if not (active_user_logged_in(req)):
            login_url = reverse('domain_login', kwargs={'domain': domain_name})
            return redirect_for_login_or_domain(req, login_url=login_url)

        couch_user = _ensure_request_couch_user(req)
        if not domain_obj.is_active:
            return _inactive_domain_response(req, domain_name)
        if domain_obj.is_snapshot:
            if not hasattr(req, 'couch_user') or not req.couch_user.is_previewer():
                raise Http404()
            return call_view()

        if couch_user.is_member_of(domain_obj, allow_enterprise=True):
            if _is_missing_two_factor(view_func, req):
                return TemplateResponse(request=req, template='two_factor/core/otp_required.html', status=403)
            elif not _can_access_project_page(req):
                return _redirect_to_project_access_upgrade(req)
            elif is_request_blocked_from_viewing_domain_due_to_sso(req, domain_obj):
                # Important! Make sure this is always the final check prior
                # to returning call_view() below
                return render_untrusted_identity_provider_for_domain_view(req, domain_obj)
            else:
                return call_view()
        elif user.is_superuser:
            if domain_obj.restrict_superusers and not _page_is_whitelisted(req.path, domain_obj.name):
                from corehq.apps.hqwebapp.views import no_permissions
                msg = "This project space restricts superuser access.  You must request an invite to access it."
                return no_permissions(req, message=msg)
            if not _can_access_project_page(req):
                return _redirect_to_project_access_upgrade(req)
            if is_request_using_sso(req):
                # We will not support SSO for superusers at this time
                return HttpResponseForbidden(
                    "SSO support is not currently available for superusers."
                )
            return call_view()
        elif couch_user.is_web_user() and domain_obj.allow_domain_requests:
            from corehq.apps.users.views.web import DomainRequestView
            return DomainRequestView.as_view()(req, *args, **kwargs)
        else:
            raise Http404

    return _inner


def _inactive_domain_response(request, domain_name):
    msg = _(
        'The project space "{domain}" has not yet been activated. '
        'Please report an issue if you think this is a mistake.'
    ).format(domain=domain_name)
    messages.info(request, msg)
    return HttpResponseRedirect(reverse("domain_select"))


def _is_missing_two_factor(view_fn, request):
    return (_two_factor_required(view_fn, request.project, request)
            and not getattr(request, 'bypass_two_factor', False)
            and not request.user.is_verified())


def _page_is_whitelisted(path, domain):
    safe_paths = {page.format(domain=domain) for page in settings.PAGES_NOT_RESTRICTED_FOR_DIMAGI}
    return path in safe_paths


def _can_access_project_page(request):
    # always allow for non-SaaS deployments
    if not settings.IS_SAAS_ENVIRONMENT:
        return True
    return has_privilege(request, privileges.PROJECT_ACCESS) or (
        hasattr(request, 'always_allow_project_access') and request.always_allow_project_access
    )


def _redirect_to_project_access_upgrade(request):
    from corehq.apps.domain.views.accounting import SubscriptionUpgradeRequiredView
    return SubscriptionUpgradeRequiredView().get(
        request, request.domain, privileges.PROJECT_ACCESS
    )


def _ensure_request_couch_user(request):
    couch_user = getattr(request, 'couch_user', None)
    if not couch_user and hasattr(request, 'user'):
        request.couch_user = couch_user = CouchUser.from_django_user(request.user)
    return couch_user


def _ensure_request_project(request):
    project = getattr(request, 'project', None)
    if not project and hasattr(request, 'domain'):
        _store_project_on_request(request, request.domain)
    return project


def active_user_logged_in(request):
    return request.user.is_authenticated and request.user.is_active


class LoginAndDomainMixin(object):

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)


def _api_key(allow_creds_in_data=True):
    api_auth_class = HQApiKeyAuthentication(allow_creds_in_data=allow_creds_in_data)

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


def _oauth2_check(scopes):
    def auth_check(request):
        oauthlib_core = get_oauthlib_core()
        # as of now, this is only used in our APIs, so explictly check that particular scope
        valid, r = oauthlib_core.verify_request(request, scopes=scopes)
        if valid:
            request.user = r.user
            return True

    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            auth = auth_check(request)
            if auth:
                return view(request, *args, **kwargs)

            response = HttpUnauthorized()
            return response
        return wrapper
    return real_decorator


def _login_or_challenge(challenge_fn, allow_cc_users=False, api_key=False,
                        allow_sessions=True, require_domain=True):
    """
    Ensure someone is logged in, or issue a challenge / failure.

    challenge_fn: a decorator function that takes in a view and returns a wrapped version of that
      view with additional "challenges" applied - namely checking authentication.
      If the "challenges" are met the decorator function should:
        1. Add a ".user" property to the request object.
        2. Call the decorated view
      If the "challenges" are not met, the decorator function should either return an
      HttpUnauthorized response, or a response allowing the caller to provide additional
      authentication details.
    allow_cc_users: authorize non-WebUser users
    allow_sessions: allow session based authorization
    require_domain: whether domain checks should be used/assumed in API request
    """
    def _outer(fn):
        if require_domain:
            @wraps(fn)
            def safe_fn_with_domain(request, domain, *args, **kwargs):
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
                            and couch_user.is_member_of(domain, allow_enterprise=True)
                        ):
                            clear_login_attempts(couch_user)
                            return fn(request, domain, *args, **kwargs)
                        else:
                            return HttpResponseForbidden()

                    return _inner(request, domain, *args, **kwargs)

            return safe_fn_with_domain
        else:
            # basically a mirror of the above implementation but for a request without a domain
            @wraps(fn)
            def safe_fn_no_domain(request, *args, **kwargs):
                if request.user.is_authenticated and allow_sessions:
                    # replaces login_and_domain_required
                    return login_required(fn)(request, *args, **kwargs)
                else:
                    # two_factor_check is removed because 2fa enforcement
                    # only happens in the context of a domain
                    @check_lockout
                    @challenge_fn
                    def _inner(request, *args, **kwargs):
                        couch_user = _ensure_request_couch_user(request)
                        if (
                            couch_user
                            and (allow_cc_users or couch_user.is_web_user())
                        ):
                            clear_login_attempts(couch_user)
                            return fn(request, *args, **kwargs)
                        else:
                            return HttpResponseForbidden()

                    return _inner(request, *args, **kwargs)
            return safe_fn_no_domain

    return _outer


def login_or_basic_ex(allow_cc_users=False, allow_sessions=True, require_domain=True):
    return _login_or_challenge(
        basicauth(),
        allow_cc_users=allow_cc_users,
        allow_sessions=allow_sessions,
        require_domain=require_domain,
    )


def login_or_basic_or_api_key_ex(allow_cc_users=False, allow_sessions=True):
    return _login_or_challenge(basic_or_api_key(), allow_cc_users=allow_cc_users, allow_sessions=allow_sessions)


def login_or_digest_ex(allow_cc_users=False, allow_sessions=True, require_domain=True):
    return _login_or_challenge(
        httpdigest,
        allow_cc_users=allow_cc_users,
        allow_sessions=allow_sessions,
        require_domain=require_domain,
    )


def login_or_formplayer_ex(allow_cc_users=False, allow_sessions=True, require_domain=True):
    return _login_or_challenge(
        formplayer_as_user_auth,
        allow_cc_users=allow_cc_users,
        allow_sessions=allow_sessions,
        require_domain=require_domain,
    )


def login_or_api_key_ex(allow_cc_users=False, allow_sessions=True, require_domain=True, allow_creds_in_data=True):
    return _login_or_challenge(
        _api_key(allow_creds_in_data=allow_creds_in_data),
        allow_cc_users=allow_cc_users,
        api_key=True,
        allow_sessions=allow_sessions,
        require_domain=require_domain,
    )


def login_or_oauth2_ex(allow_cc_users=False, allow_sessions=True, require_domain=True, oauth_scopes=None):
    oauth_scopes = oauth_scopes or ['access_apis']
    return _login_or_challenge(
        _oauth2_check(oauth_scopes),
        allow_cc_users=allow_cc_users,
        api_key=True,
        allow_sessions=allow_sessions,
        require_domain=require_domain,
    )


def get_multi_auth_decorator(default, allow_formplayer=False, oauth_scopes=None, allow_creds_in_data=True):
    """
    :param allow_formplayer: If True this will allow one additional auth mechanism which is used
         by Formplayer:

         - formplayer auth: for SMS forms there is no active user involved in the session and so
             formplayer can not use the session cookie to auth. To allow formplayer access to the
             endpoints we validate each formplayer request using a shared key. See the auth
             function for more details.
    """
    oauth_scopes = oauth_scopes or ['access_apis']

    def decorator(fn):
        @wraps(fn)
        def _inner(request, *args, **kwargs):
            authtype = determine_authtype_from_request(request, default=default)
            if authtype == FORMPLAYER and not allow_formplayer:
                auth_logger.info(
                    "Request rejected reason=%s request=%s",
                    "formplayer_auth:not_enabled_for_request", request.path
                )
                return HttpResponseForbidden()
            request.auth_type = authtype  # store auth type on request for access in views
            function_wrapper = get_auth_decorator_map(
                allow_cc_users=True,
                oauth_scopes=oauth_scopes,
                allow_creds_in_data=allow_creds_in_data,
            )[authtype]
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
    return wraps(view_func)(wrapped_view)


def api_auth(*, allow_creds_in_data=True, oauth_scopes=None):
    """Allow any auth type basic, digest, session, apikey, or oauth"""
    return get_multi_auth_decorator(
        default=DIGEST,
        oauth_scopes=oauth_scopes,
        allow_creds_in_data=allow_creds_in_data,
    )


# Use these decorators on views to allow sesson-auth or an extra authorization method
login_or_digest = login_or_digest_ex()
login_or_basic = login_or_basic_ex()
login_or_api_key = login_or_api_key_ex()

api_key_auth = login_or_api_key_ex(allow_sessions=False)

basic_auth_or_try_api_key_auth = login_or_basic_or_api_key_ex(allow_sessions=False)


def get_auth_decorator_map(
        allow_cc_users=False,
        require_domain=True,
        allow_sessions=True,
        oauth_scopes=None,
        allow_creds_in_data=True,
):
    # get a mapped set of decorators for different auth types with the specified parameters
    oauth_scopes = oauth_scopes or ['access_apis']
    decorator_function_kwargs = {
        'allow_cc_users': allow_cc_users,
        'require_domain': require_domain,
        'allow_sessions': allow_sessions,
    }
    return {
        DIGEST: login_or_digest_ex(**decorator_function_kwargs),
        BASIC: login_or_basic_ex(**decorator_function_kwargs),
        API_KEY: login_or_api_key_ex(allow_creds_in_data=allow_creds_in_data,
                                     **decorator_function_kwargs),
        OAUTH2: login_or_oauth2_ex(oauth_scopes=oauth_scopes, **decorator_function_kwargs),
        FORMPLAYER: login_or_formplayer_ex(**decorator_function_kwargs),
    }


def two_factor_check(view_func, api_key):
    def _outer(fn):
        @wraps(fn)
        def _inner(request, domain, *args, **kwargs):
            domain_obj = Domain.get_by_name(domain)
            _ensure_request_couch_user(request)
            if (
                not api_key and
                not getattr(request, 'skip_two_factor_check', False) and
                domain_obj and
                _two_factor_required(view_func, domain_obj, request)
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
            if api_key:
                request.bypass_two_factor = True
            return fn(request, domain, *args, **kwargs)
        return _inner
    return _outer


def _two_factor_required(view_func, domain_obj, request):
    """
    Check if Two Factor Authentication is required.
    :param view_func: the view function being accessed
    :param domain_obj: Domain instance associated with the view
    :param request: Request
    :return: Boolean (True if 2FA is required)
    """
    exempt = getattr(view_func, 'two_factor_exempt', False)
    if exempt:
        return False
    if not request.couch_user:
        return False
    if is_request_using_sso(request):
        # SSO authenticated users manage two-factor auth on the Identity Provider
        # level, so CommCare HQ does not attempt 2FA with them. This is one of
        # the reasons we require that domains establish TrustedIdentityProvider
        # relationships.
        return False
    return (
        # If a user is a superuser, then there is no two_factor_disabled loophole allowed.
        # If you lose your phone, you have to give up superuser privileges
        # until you have two factor set up again.
        settings.REQUIRE_TWO_FACTOR_FOR_SUPERUSERS and request.couch_user.is_superuser
    ) or (
        # For other policies requiring two factor auth,
        # allow the two_factor_disabled loophole for people who have lost their phones
        # and need time to set up two factor auth again.
        (domain_obj.two_factor_auth or TWO_FACTOR_SUPERUSER_ROLLOUT.enabled(request.couch_user.username))
        and not request.couch_user.two_factor_disabled
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
    @_api_key()
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

        return view_func(request, *args, **kwargs)
    return _inner


def active_domains_required(view_func):
    from corehq.apps.registration.views import registration_default

    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        if not Domain.active_for_user(request.user):
            return registration_default(request)

        return view_func(request, *args, **kwargs)

    return _inner


def check_lockout(fn):
    @wraps(fn)
    def _inner(request, *args, **kwargs):
        username, password = get_username_and_password_from_request(request)
        if not username:
            return fn(request, *args, **kwargs)

        user = CouchUser.get_by_username(username)
        if user and user.is_locked_out():
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
                _page_is_whitelisted(request.path, domain_name) and request.user.is_superuser
            ) and not request.couch_user.is_domain_admin(domain_name):
                return HttpResponseRedirect(reverse(redirect_page_name))
            return view_func(request, domain_name, *args, **kwargs)

        return _inner
    return _outer


def require_superuser_or_contractor(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        user = request.user
        if ((IS_CONTRACTOR.enabled(user.username) or user.is_superuser)
                and not is_request_using_sso(request)):
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(reverse("no_permissions"))

    return _inner


def require_superuser(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        user = request.user
        if user.is_superuser and not is_request_using_sso(request):
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(reverse("no_permissions"))

    return _inner


# Parallel to what we did with login_and_domain_required, above
domain_admin_required = domain_admin_required_ex()
cls_domain_admin_required = cls_to_view(additional_decorator=domain_admin_required)

########################################################################################################
cls_require_superusers = cls_to_view(additional_decorator=require_superuser)
cls_require_superuser_or_contractor = cls_to_view(additional_decorator=require_superuser_or_contractor)


def check_domain_migration(view_func):
    def wrapped_view(request, domain, *args, **kwargs):
        if DATA_MIGRATION.enabled(domain):
            auth_logger.info(
                "Request rejected domain=%s reason=%s request=%s",
                domain, "flag:migration", request.path
            )
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
                len(args) > 2
                and isinstance(args[0], View)
                and isinstance(args[1], HttpRequest)
                and isinstance(args[2], str)
            ):
                # class-based view; args == (self, request, domain, ...)
                domain = args[2]
            elif (
                len(args) > 1
                and isinstance(args[0], HttpRequest)
                and isinstance(args[1], str)
            ):
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
