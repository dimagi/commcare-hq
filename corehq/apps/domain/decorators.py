# Standard Library imports
import base64
from functools import wraps
import logging

# Django imports
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.utils.http import urlquote
from django.utils.translation import ugettext as _

# External imports
from django_digest.decorators import httpdigest
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege

from django.http import HttpResponse
from django.contrib.auth import authenticate, login

# CCHQ imports
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.users.models import CouchUser
from corehq import privileges

########################################################################################################
from corehq.toggles import IS_DEVELOPER

logger = logging.getLogger(__name__)

REDIRECT_FIELD_NAME = 'next'

def load_domain(req, domain):
    domain_name = normalize_domain_name(domain)
    domain = Domain.get_by_name(domain_name)
    req.project = domain
    req.can_see_organization = True
    try:
        ensure_request_has_privilege(req, privileges.CROSS_PROJECT_REPORTS)
    except PermissionDenied:
        req.can_see_organization = False
    return domain_name, domain

########################################################################################################

def _redirect_for_login_or_domain(request, redirect_field_name, login_url):
    path = urlquote(request.get_full_path())
    nextURL = '%s?%s=%s' % (login_url, redirect_field_name, path)
    return HttpResponseRedirect(nextURL)


def domain_specific_login_redirect(request, domain):
    project = Domain.get_by_name(domain)
    login_url = reverse('login', kwargs={'domain_type': project.domain_type})
    return _redirect_for_login_or_domain(request, 'next', login_url)


def login_and_domain_required(view_func):
    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        user = req.user
        domain_name, domain = load_domain(req, domain)
        if domain:
            if user.is_authenticated() and user.is_active:
                if not domain.is_active:
                    msg = _((
                        'The domain "{domain}" has been deactivated. '
                        'Please report an issue if you think this is a mistake.'
                    ).format(domain=domain_name))
                    messages.info(req, msg)
                    return HttpResponseRedirect(reverse("domain_select"))
                if hasattr(req, "couch_user"):
                    couch_user = req.couch_user # set by user middleware
                else:
                    # some views might not have this set
                    couch_user = CouchUser.from_django_user(user)
                if couch_user.is_member_of(domain) or domain.is_public:
                    return view_func(req, domain_name, *args, **kwargs)
                elif user.is_superuser and not domain.restrict_superusers:
                    # superusers can circumvent domain permissions.
                    return view_func(req, domain_name, *args, **kwargs)
                elif domain.is_snapshot:
                    # snapshots are publicly viewable
                    return require_previewer(view_func)(req, domain_name, *args, **kwargs)
                else:
                    raise Http404
            else:
                login_url = reverse('domain_login', kwargs={'domain': domain})
                return _redirect_for_login_or_domain(req, REDIRECT_FIELD_NAME, login_url)
        else:
            msg = _(('The domain "{domain}" was not found.').format(domain=domain_name))
            raise Http404(msg)
    return _inner


class LoginAndDomainMixin(object):
    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)


def basicauth(realm=''):
    # stolen and modified from: https://djangosnippets.org/snippets/243/
    def real_decorator(view):
        def wrapper(request, *args, **kwargs):
            if 'HTTP_AUTHORIZATION' in request.META:
                auth = request.META['HTTP_AUTHORIZATION'].split()
                if len(auth) == 2:
                    if auth[0].lower() == "basic":
                        uname, passwd = base64.b64decode(auth[1]).split(':', 1)
                        user = authenticate(username=uname, password=passwd)
                        if user is not None and user.is_active:
                            login(request, user)
                            request.user = user
                            return view(request, *args, **kwargs)

            # Either they did not provide an authorization header or
            # something in the authorization attempt failed. Send a 401
            # back to them to ask them to authenticate.
            response = HttpResponse()
            response.status_code = 401
            response['WWW-Authenticate'] = 'Basic realm="%s"' % realm
            return response
        return wrapper
    return real_decorator


def _login_or_challenge(challenge_fn, allow_cc_users=False):
    # ensure someone is logged in, or challenge
    # challenge_fn should itself be a decorator that can handle authentication
    def _outer(fn):
        def safe_fn(request, domain, *args, **kwargs):
            if not request.user.is_authenticated():
                @challenge_fn
                def _inner(request, domain, *args, **kwargs):
                    request.couch_user = couch_user = CouchUser.from_django_user(request.user)
                    if (allow_cc_users or couch_user.is_web_user()) and couch_user.is_member_of(domain):
                        return fn(request, domain, *args, **kwargs)
                    else:
                        return HttpResponseForbidden()

                return _inner(request, domain, *args, **kwargs)
            else:
                return login_and_domain_required(fn)(request, domain, *args, **kwargs)
        return safe_fn
    return _outer


def login_or_digest_ex(allow_cc_users=False):
    return _login_or_challenge(httpdigest, allow_cc_users=allow_cc_users)

login_or_digest = login_or_digest_ex()


def login_or_basic_ex(allow_cc_users=False):
    return _login_or_challenge(basicauth(), allow_cc_users=allow_cc_users)

login_or_basic = login_or_basic_ex()


# For views that are inside a class
# todo where is this being used? can be replaced with decorator below
def cls_login_and_domain_required(func):
    def __outer__(cls, request, domain, *args, **kwargs):
        @login_and_domain_required
        def __inner__(request, domain, *args, **kwargs):
            return func(cls, request, domain, *args, **kwargs)
        return __inner__(request, domain, *args, **kwargs)
    return __outer__

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

def login_required(view_func):
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        login_url = reverse('login')
        user = request.user
        if not (user.is_authenticated() and user.is_active):
            return _redirect_for_login_or_domain(request,
                    REDIRECT_FIELD_NAME, login_url)

        # User's login and domain have been validated - it's safe to call the view function
        return view_func(request, *args, **kwargs)
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
        @wraps(view_func)
        def _inner(request, domain, *args, **kwargs):
            if not hasattr(request, 'couch_user'):
                raise Http404()
            if not request.couch_user.is_web_user():
                raise Http404()
            domain_name, domain = load_domain(request, domain)
            if not domain:
                raise Http404()
            if not request.couch_user.is_domain_admin(domain_name):
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

