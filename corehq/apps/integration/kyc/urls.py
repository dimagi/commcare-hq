from django.urls import re_path as url

from corehq.apps.integration.kyc.views import (
    KycConfigurationView,
    KycVerificationReportView,
)


urlpatterns = [
    url(r'^configure/$', KycConfigurationView.as_view(),
        name=KycConfigurationView.urlname),
    url(r'^verify/$', KycVerificationReportView.as_view(),
        name=KycVerificationReportView.urlname),
]
