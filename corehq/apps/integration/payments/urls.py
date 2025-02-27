from django.urls import re_path as url

from corehq.apps.integration.payments.views import (
    PaymentsVerificationReportView,
)


urlpatterns = [
    url(r'^verify/$', PaymentsVerificationReportView.as_view(), name=PaymentsVerificationReportView.urlname),
]
