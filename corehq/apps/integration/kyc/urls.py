from django.urls import re_path as url

from corehq.apps.integration.kyc.views import KycConfigurationView


urlpatterns = [
    url(r'^configure/$', KycConfigurationView.as_view(),
        name=KycConfigurationView.urlname),
]
