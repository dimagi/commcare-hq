import sys
from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template
from django.core.urlresolvers import reverse
from django.contrib.auth.views import password_reset
from django.shortcuts import render_to_response
from django.template import RequestContext
import settings

#
# After much reading, I discovered that Django matches URLs derived from the environment
# variable PATH_INFO. This is set by your webserver, so any misconfiguration there will
# mess this up. In Apache, the WSGIScriptAliasMatch pulls off the mount point directory,
# and puts everything that follows it into PATH_INFO. Those (mount-point-less) paths are
# what is matched in urlpatterns.
#

# All of these auth functions have custom templates in registration/, with the default names they expect.
#
# Django docs on password reset are weak. See these links instead:
#
# http://streamhacker.com/2009/09/19/django-ia-auth-password-reset/
# http://www.rkblog.rk.edu.pl/w/p/password-reset-django-10/
# http://blog.montylounge.com/2009/jul/12/django-forgot-password/
#
# Note that the provided password reset function raises SMTP errors if there's any
# problem with the mailserver. Catch that more elegantly with a simple wrapper.

def exception_safe_password_reset(request, *args, **kwargs):
    try:
        return password_reset(request, *args, **kwargs)                
    except: 
        vals = {'error_msg':'There was a problem with your request',
                'error_details':sys.exc_info(),
                'show_homepage_link': 1 }
        return render_to_response('error.html', vals, context_instance = RequestContext(request))   


# auth templates are normally in 'registration,'but that's too confusing a name, given that this app has
# both user and domain registration. Move them somewhere more descriptive.

def auth_pages_path(page):
    return {'template_name':'login_and_password/' + page}


urlpatterns = patterns( 
        'domain.views',        
        url(r'^domain/tos/$', direct_to_template, {'template': 'tos.html'}, name='tos'),
                        
        url(r'^domain/select/$', 'select', name='domain_select'),
        
        # Fancy regexp lets us get URLs that have an optional path component after registration_request/.
        # The optional component is considered to begin with a /, and the whole URL ends with a /, so that the
        # slash-append mechanism in Django works as desired. The key to making this work is to take the optional
        # component's leading slash in a non-capturing group, denoted by ?:, and pick up the named param in 
        # a named capturing group, denoted by ?P<kind>
        url(r'^domain/registration_request(?:/(?P<kind>\w+))?/$', 'registration_request', name='domain_registration_request'),                                   
        
        # Same trick as above - make GUID optional
        url(r'^domain/registration_confirm(?:/(?P<guid>\w+))?/$', 'registration_confirm',  name='domain_registration_confirm'),        
        url(r'^domain/registration_resend_confirm_email/$', 'registration_resend_confirm_email', name='domain_registration_resend_confirm_email'),
        
        # domain admin functions
        url(r'^domain/admin/$', 'admin_main', name='domain_admin_main'),
        url(r'^domain/admin/user_list/$', 'user_list', name='domain_user_list'),
        url(r'^domain/admin/edit_user/(?P<user_id>\d{1,10})/$', 'edit_user', name='domain_edit_user'),
        url(r'^accounts/admin_own/$', 'admin_own_account_main', name='admin_own_account_main'),
        url(r'^accounts/admin_own/update/$', 'admin_own_account_update', name='admin_own_account_update')) \
        + patterns('django.contrib.auth.views',
        url(r'^accounts/password_change/$', 'password_change', auth_pages_path('password_change_form.html'), name='password_change'),
        url(r'^accounts/password_change_done/$', 'password_change_done', auth_pages_path('password_change_done.html') ),                                                
        url(r'^accounts/password_reset_email/$', exception_safe_password_reset, auth_pages_path('password_reset_form.html'), name='password_reset_email'),
        url(r'^accounts/password_reset_email/done/$', 'password_reset_done', auth_pages_path('password_reset_done.html') ),
        url(r'^accounts/password_reset_confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 'password_reset_confirm', auth_pages_path('password_reset_confirm.html') ),
        url(r'^accounts/password_reset_confirm/done/$', 'password_reset_complete', auth_pages_path('password_reset_complete.html') ) 
        )
        
        
