from django.conf.urls import url

from corehq.apps.integration.views import (
    BiometricIntegrationView,
)


urlpatterns = [
    url(r'^biometric/$', BiometricIntegrationView.as_view(),
        name=BiometricIntegrationView.urlname),
]
