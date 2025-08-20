from django.urls import re_path as url

from corehq.apps.integration.kyc.views import (
    KycConfigurationView,
    KycVerificationReportView,
    KycVerificationTableView,
)


urlpatterns = [
    url(r'^configure/$', KycConfigurationView.as_view(),
        name=KycConfigurationView.urlname),
    url(r'^verify/$', KycVerificationReportView.as_view(),
        name=KycVerificationReportView.urlname),
    url(r'^verify/table/$', KycVerificationTableView.as_view(),
        name=KycVerificationTableView.urlname),
]
