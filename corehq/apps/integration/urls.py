from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.integration.views import (
    BiometricIntegrationView,
)


urlpatterns = [
    url(r'^biometric/$', BiometricIntegrationView.as_view(),
        name=BiometricIntegrationView.urlname),
]
