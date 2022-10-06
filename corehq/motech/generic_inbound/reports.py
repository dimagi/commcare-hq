from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.toggles import GENERIC_INBOUND_API

from .models import RequestLog


class ApiRequestLogReport(GenericTabularReport):
    name = gettext_lazy('Inbound API Request Logs')
    slug = 'api_request_log_report'
    base_template = "reports/base_template.html"
    section_name = gettext_lazy('Project Settings')
    dispatcher = DomainReportDispatcher
    ajax_pagination = True
    sortable = False

    fields = []

    toggles = [GENERIC_INBOUND_API]

    @classmethod
    def allow_access(cls, request):
        return request.couch_user.is_domain_admin()

    @property
    def total_records(self):
        return self._queryset.count()

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("API")),
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("Status")),
            DataTablesColumn(_("Response")),
        )

    @cached_property
    def _queryset(self):
        return RequestLog.objects.filter(
            domain=self.domain,
        )

    @property
    def rows(self):
        status_labels = dict(RequestLog.Status.choices)
        for log in self._queryset[self.pagination.start:self.pagination.end]:
            yield [
                log.api.name,
                log.timestamp,
                status_labels[log.status],
                log.response_status,
            ]
