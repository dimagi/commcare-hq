from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.registration.views',
    url(r'^$', 'register_user', name='registration_new_user'),
    #registration_first_time_domain, register_domain
    url(r'^domain/$', 'register_domain', name='registration_domain'),
    url(r'^organization/$', 'register_org', name='registration_org'),
    url(r'^domain/confirm(?:/(?P<guid>\w+))?/$', 'confirm_domain', name='registration_confirm_domain'),
    url(r'^domain/resend$', 'resend_confirmation', name='registration_resend_domain_confirmation')
)