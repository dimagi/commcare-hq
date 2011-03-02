"""
URLconf for registration and activation, based on django-registration's
default backend.

"""

from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

from django_user_registration.views import activate
from django_user_registration.views import register
from corehq.apps.domain.user_registration_backend import activate_by_form


urlpatterns = patterns('',
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
                           { 'backend': 'corehq.apps.domain.user_registration_backend.UserRegistersSelfBackend' },
                           name='registration_activate_user_inputs_data'),                                                   
                                                                   
                       url(r'^activate/complete(?:/(?P<caller>\w+))?(?:/(?P<account>\w+))?/$',
                           direct_to_template,
                           { 'template': 'domain/user_registration/activation_complete.html' },
                           name='registration_activation_complete')                                            
                       )
