from django.conf.urls import url

from corehq.apps.integration.views import BiometricIntegrationView, dialer_view, DialerSettingsView

settings_patterns = [
    url(r'^biometric/$', BiometricIntegrationView.as_view(),
        name=BiometricIntegrationView.urlname),
    url(r'^dialer/$', DialerSettingsView.as_view(), name=DialerSettingsView.urlname),
]

urlpatterns = [
    url(r'dialer/$', dialer_view, name="dialer_view"),
]
