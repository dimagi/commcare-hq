from django.urls import re_path as url

from corehq.apps.registration.views import (
    ProcessRegistrationView,
    RegisterDomainView,
    UserRegistrationView,
    confirm_domain,
    eula_agreement,
    registration_default,
    resend_confirmation,
    send_mobile_reminder,
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
    url(r'^mobile_reminder/', send_mobile_reminder,
        name="send_mobile_reminder"),
    url(r'^resend/$', resend_confirmation,
        name='registration_resend_domain_confirmation'),
    url(r'^eula_agreement/$', eula_agreement, name="agree_to_eula"),
]
