from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.registration.views',
    url(r'^$', 'register_user', name='registration_new_user'),
    url(r'^domain/$', 'register_domain', name='registration_first_time_domain'),
    url(r'^domain/confirm(?:/(?P<guid>\w+))?/$', 'confirm_domain', name='registration_confirm_domain'),
    url(r'^domain/resend$', 'resend_confirmation', name='registration_resend_domain_confirmation')
)