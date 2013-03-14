from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.registration.views',
    url(r'^$', 'registration_default', name='registration_default'),
    url(r'^user/(?P<domain_type>\w+)?$', 'register_user', name='register_user'),
    url(r'^domain/(?P<domain_type>\w+)?$', 'register_domain', name='registration_domain'),
    url(r'^organization/$', 'register_org', name='registration_org'),
    url(r'^domain/confirm(?:/(?P<guid>\w+))?/$', 'confirm_domain', name='registration_confirm_domain'),
    url(r'^resend/$', 'resend_confirmation', name='registration_resend_domain_confirmation'),
    url(r'^eula_agreement/$', 'eula_agreement', name="agree_to_eula"),
)
