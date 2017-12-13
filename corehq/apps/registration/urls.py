from __future__ import absolute_import
from django.conf.urls import url

from corehq.apps.registration.views import (
    RegisterDomainView,
    UserRegistrationView,
    ProcessRegistrationView,
    registration_default,
    confirm_domain,
    resend_confirmation,
    eula_agreement,
)


urlpatterns = [
    url(r'^$', registration_default, name='registration_default'),
    url(r'^user/?$', UserRegistrationView.as_view(),
        name=UserRegistrationView.urlname),
    url(r'^process/?$', ProcessRegistrationView.as_view(),
        name=ProcessRegistrationView.urlname),
    url(r'^domain/$', RegisterDomainView.as_view(), name='registration_domain'),
    url(r'^domain/confirm(?:/(?P<guid>\w+))?/$', confirm_domain,
        name='registration_confirm_domain'),
    url(r'^resend/$', resend_confirmation,
        name='registration_resend_domain_confirmation'),
    url(r'^eula_agreement/$', eula_agreement, name="agree_to_eula"),
]
