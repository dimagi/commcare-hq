"""
URLconf for registration and activation, based on django-registration's
default backend.

"""

from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

from domain.decorators import login_and_domain_required, domain_admin_required
from user_registration.views import activate
from user_registration.views import register
from domain.user_registration_backend import activate_by_form, register_with_possible_errors, register_admin_does_all


urlpatterns = patterns('',
                       
                       # Registration of new users might fail, but the default 'register' doesn't
                       # handle this possibility. Had to rewrite it.
                       url(r'^register/invite_user/$',
                           register_with_possible_errors,
                           { 'backend': 'domain.user_registration_backend.UserRegistersSelfBackend',
                             'template_name':'domain/user_registration/registration_invite_form.html' },
                           name='registration_invite_user'),
                        
                        url(r'^register/admin_does_all/$',
                            # Traditional view - not done in the registration framework
                           register_admin_does_all,                           
                           name='registration_admin_does_all'),
                       url(r'^register/complete/$',
                           # Normally don't like login decorators in URLConfs, but there's no 
                           # choice here - we're using a generic view
                           login_and_domain_required(domain_admin_required(direct_to_template)),
                           { 'template': 'domain/user_registration/registration_request_complete.html' },
                           name='registration_request_complete'),
                        url(r'^register/closed/$',
                           direct_to_template,
                           { 'template': 'domain/user_registration/registration_closed.html' },
                           name='registration_disallowed'),      

                       # Activation keys get matched by \w+ instead of the more specific
                       # [a-fA-F0-9]{40} because a bad activation key should still get to the view;
                       # that way it can return a sensible "invalid key" message instead of a
                       # confusing 404.
                    
                       # Because our main activation workflow relies on the user adding new data
                       # at activation time, we can't use the default 'activate.' Had to rewrite it.             
                       url(r'^activate/user_inputs_data/(?P<activation_key>\w+)/$',
                           activate_by_form,
                           { 'backend': 'domain.user_registration_backend.UserRegistersSelfBackend' },
                           name='registration_activate_user_inputs_data'),                                                   
                                                                   
                       url(r'^activate/complete(?:/(?P<caller>\w+))?(?:/(?P<account>\w+))?/$',
                           direct_to_template,
                           { 'template': 'domain/user_registration/activation_complete.html' },
                           name='registration_activation_complete')                                            
                       )
