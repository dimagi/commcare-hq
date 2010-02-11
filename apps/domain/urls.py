from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

#
# After much reading, I discovered that Django matches URLs derived from the environment
# variable PATH_INFO. This is set by your webserver, so any misconfiguration there will
# mess this up. In Apache, the WSGIScriptAliasMatch pulls off the mount point directory,
# and puts everything that follows it into PATH_INFO. Those (mount-point-less) paths are
# what is matched in urlpatterns.
#

urlpatterns = patterns( 
        'domain.views',        
        url(r'^domain/home/$', 'homepage', name='homepage'),
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
        )


