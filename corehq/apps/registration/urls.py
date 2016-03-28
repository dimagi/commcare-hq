from django.conf.urls import *

from corehq.apps.registration.views import RegisterDomainView

urlpatterns = patterns('corehq.apps.registration.views',
    url(r'^$', 'registration_default', name='registration_default'),
    url(r'^user/?$', 'register_user', name='register_user'),
    url(r'^domain/$', RegisterDomainView.as_view(), name='registration_domain'),
    url(r'^domain/confirm(?:/(?P<guid>\w+))?/$', 'confirm_domain', name='registration_confirm_domain'),
    url(r'^resend/$', 'resend_confirmation', name='registration_resend_domain_confirmation'),
    url(r'^eula_agreement/$', 'eula_agreement', name="agree_to_eula"),
)
