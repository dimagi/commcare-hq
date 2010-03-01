from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.http import urlquote

########################################################################################################

REDIRECT_FIELD_NAME = 'next'

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

def login_and_domain_required_ex( redirect_field_name = REDIRECT_FIELD_NAME,                                  
                                  login_url = None,
                                  domain_select_url = None ) :                                  

    def _outer( view_func ): 
        def _inner(request, *args, **kwargs):
                
            #######################################################################                
            #    
            # Can't change vals in closure variables - need to use new locals      
                              
            if login_url is None:
                l_login_url = settings.LOGIN_URL
            else:
                l_login_url = login_url
                
            if domain_select_url is None:
                l_domain_select_url = settings.DOMAIN_SELECT_URL
            else:
                l_domain_select_url = domain_select_url

            #######################################################################
            # 
            # The actual meat of the decorator
            
            user = request.user
            if not (user.is_authenticated() and user.is_active):
                return _redirect_for_login_or_domain( request, redirect_field_name, l_login_url)

            # If the user has an obviously-valid domain, it was already set in the domain middleware.
            # If it's None, send the user to select a domain. If none are available to him/her,
            # that'll be caught in the selection form.
                        
            if user.selected_domain is None:
                return _redirect_for_login_or_domain( request, redirect_field_name, l_domain_select_url )
            
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
# @login_and_domain_required
#

login_and_domain_required = login_and_domain_required_ex()

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
        def _inner(request, *args, **kwargs):
            if not request.user.is_selected_dom_admin():
                return HttpResponseRedirect(reverse(redirect_page_name))
            return view_func(request, *args, **kwargs)

        _inner.__name__ = view_func.__name__
        _inner.__doc__ = view_func.__doc__
        _inner.__module__ = view_func.__module__
        _inner.__dict__.update(view_func.__dict__)
        
        return _inner
    return _outer

# Parallel to what we did with login_and_domain_required, above
domain_admin_required = domain_admin_required_ex()

########################################################################################################
    