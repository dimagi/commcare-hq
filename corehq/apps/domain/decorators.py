from functools import wraps
from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden
from django.utils.http import urlquote

########################################################################################################
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.users.models import CouchUser, PublicUser
from django_digest.decorators import httpdigest

REDIRECT_FIELD_NAME = 'next'

def load_domain(req, domain):
    domain_name = normalize_domain_name(domain)
    domain = Domain.get_by_name(domain_name)
    req.project = domain
    return domain_name, domain

########################################################################################################

def _redirect_for_login_or_domain(request, redirect_field_name, where):
    path = urlquote(request.get_full_path())
    nextURL = '%s?%s=%s' % (where, redirect_field_name, path)
    return HttpResponseRedirect(nextURL)

########################################################################################################
#
# Decorator that checks to see if user is loggd in and a domain is set.
#
# Unfortunately, there's no good way to combine this with the login_required decorator,
# because what we want to do is to test for domains just after authentication, but
# right before final page rendering. The provided login code doesn't provide the right hooks
# to do that, so we have to roll our own combo decorator.
#
# Also, because we are using default arguments, we need to have a three-layer
# decorator. Python treats decorators that take arguments differently than those that
# don't; essentially, login_and_domain_required_ex is a factory function that produces 
# a decorator (the function _outer). The parameters passed in to login_and_domain_required_ex
# just serve as a closure that's referred to in the _inner function that finally wraps 
# view_func.
#
# This means that we always have to put parentheses after login_and_domain_required_ex,
# even if we intend to use only the default arguments. It looks a bit funny to do so,
# but it won't work otherwise. 

# As syntactic sugar, just below I define a more-conventional looking version that doesn't 
# require parentheses, but also can't take any changes to the default params. That's not 
# a big problem - most of the time the default values are fine.

# Can't put reverse() in any code that executes upon file import, which means it can't go
# in default parms of functions that are called at import (such as the call to login_and_domain_required()
# below. This is because the files are imported during initialization of the urlconfs, and
# the call to reverse happens before intialization is finished, so it fails. Need to delay 
# the call to reverse until post-initialization, which means until during the first actual call
# into _inner().

def login_and_domain_required_ex(redirect_field_name=REDIRECT_FIELD_NAME, login_url=settings.LOGIN_URL):
    def _outer(view_func):
        @wraps(view_func)
        def _inner(req, domain, *args, **kwargs):
            user = req.user
            domain_name, domain = load_domain(req, domain)
            if domain and user.is_authenticated() and user.is_active:
                if not domain.is_active:
                    return HttpResponseRedirect(reverse("domain_select"))
                if hasattr(req, "couch_user"):
                    couch_user = req.couch_user # set by user middleware
                else: 
                    # some views might not have this set
                    couch_user = CouchUser.from_django_user(user)
                if couch_user.is_member_of(domain):
                    return view_func(req, domain_name, *args, **kwargs)
                elif user.is_superuser:
                    # superusers can circumvent domain permissions.
                    return view_func(req, domain_name, *args, **kwargs)
                elif domain.is_snapshot:
                    # snapshots are publicly viewable
                    return require_previewer(view_func)(req, domain_name, *args, **kwargs)
                else:
                    raise Http404
            else:
                return _redirect_for_login_or_domain(req, redirect_field_name, login_url)
        
        return _inner
    return _outer

#
# This works without parentheses:
# @login_and_domain_required
#

login_and_domain_required = login_and_domain_required_ex()

def login_or_digest_ex(allow_cc_users=False):
    def _outer(fn):
        def safe_fn(request, domain, *args, **kwargs):
            if not request.user.is_authenticated():
                def _inner(request, domain, *args, **kwargs):
                    request.couch_user = couch_user = CouchUser.from_django_user(request.user)
                    if (allow_cc_users or couch_user.is_web_user()) and couch_user.is_member_of(domain):
                        return fn(request, domain, *args, **kwargs)
                    else:
                        return HttpResponseForbidden()
        
                return httpdigest(_inner)(request, domain, *args, **kwargs)
            else:
                return login_and_domain_required(fn)(request, domain, *args, **kwargs)
        return safe_fn
    return _outer

login_or_digest = login_or_digest_ex()

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

# when requiring a specific domain
def require_domain(domain):
    return login_and_domain_required_ex(require_domain=domain)


########################################################################################################
#
# Auth's login_required decorator is broken - it tries to get LOGIN_URL too early, which messes up
# URLConf parsing (same problem described above). So, we need to define a delayed-eval login_required
# call, too. We'll give it a distinguished name, so people are less confused.

def login_required_ex( redirect_field_name = REDIRECT_FIELD_NAME,                                  
                                  login_url = None ) :                                  

    def _outer( view_func ): 
        def _inner(request, *args, **kwargs):
                
            #######################################################################                
            #    
            # Can't change vals in closure variables - need to use new locals      
                              
            if login_url is None:
                l_login_url = settings.LOGIN_URL
            else:
                l_login_url = login_url

            #######################################################################
            # 
            # The actual meat of the decorator
            
            user = request.user
            if not (user.is_authenticated() and user.is_active):
                return _redirect_for_login_or_domain( request, redirect_field_name, l_login_url)
            
            # User's login and domain have been validated - it's safe to call the view function
            return view_func(request, *args, **kwargs)

        _inner.__name__ = view_func.__name__
        _inner.__doc__ = view_func.__doc__
        _inner.__module__ = view_func.__module__
        _inner.__dict__.update(view_func.__dict__)
        
        return _inner
    return _outer

#
# This works without parentheses:
# @login_required
#

login_required_late_eval_of_LOGIN_URL = login_required_ex()

########################################################################################################
#
# Have to write this to be sure this decorator still works if DOMAIN_NOT_ADMIN_REDIRECT_PAGE_NAME
# is not defined - people may forget to do this, because it's not a standard, defined Django 
# config setting

def domain_admin_required_ex( redirect_page_name = None ):
    if redirect_page_name is None:
        redirect_page_name = getattr(settings, 'DOMAIN_NOT_ADMIN_REDIRECT_PAGE_NAME', 'homepage')                                                                                                 
    def _outer( view_func ): 
        def _inner(request, domain, *args, **kwargs):
            if not hasattr(request, 'couch_user'):
                raise Http404
            if not request.couch_user.is_web_user():
                raise Http404
            domain_name, domain = load_domain(request, domain)
            if not request.couch_user.is_domain_admin(domain_name):
                return HttpResponseRedirect(reverse(redirect_page_name))
            return view_func(request, domain_name, *args, **kwargs)

        _inner.__name__ = view_func.__name__
        _inner.__doc__ = view_func.__doc__
        _inner.__module__ = view_func.__module__
        _inner.__dict__.update(view_func.__dict__)
        
        return _inner
    return _outer

# Parallel to what we did with login_and_domain_required, above
domain_admin_required = domain_admin_required_ex()
cls_domain_admin_required = cls_to_view(additional_decorator=domain_admin_required)

########################################################################################################
# couldn't figure how to call reverse, so login_url is the actual url
require_superuser = permission_required("is_superuser", login_url='/no_permissions/')
cls_require_superusers = cls_to_view(additional_decorator=require_superuser)

def require_previewer(view_func):
    def shim(request, *args, **kwargs):
        if not hasattr(request, 'couch_user') or not request.couch_user.is_previewer():
            raise Http404
        else:
            return view_func(request, *args, **kwargs)
    return shim

cls_require_previewer = cls_to_view(additional_decorator=require_previewer)
