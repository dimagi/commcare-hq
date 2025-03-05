from django.urls import re_path as url

from corehq.apps.integration.payments.views import (
    PaymentsVerificationReportView, PaymentsVerificationTableView,
)


urlpatterns = [
    url(r'^verify/$', PaymentsVerificationReportView.as_view(), name=PaymentsVerificationReportView.urlname),
    url(r'^verify/table/$', PaymentsVerificationTableView.as_view(), name=PaymentsVerificationTableView.urlname),
]
