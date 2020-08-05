from django.conf.urls import url

from corehq.apps.integration.views import (
    BiometricIntegrationView,
    dialer_view,
    DialerSettingsView,
    HmacCalloutSettingsView,
)

settings_patterns = [
    url(r'^biometric/$', BiometricIntegrationView.as_view(),
        name=BiometricIntegrationView.urlname),
    url(r'^dialer/$', DialerSettingsView.as_view(), name=DialerSettingsView.urlname),
    url(r'^signed_callout/$', HmacCalloutSettingsView.as_view(), name=HmacCalloutSettingsView.urlname),
]

urlpatterns = [
    url(r'dialer/$', dialer_view, name="dialer_view"),
]
