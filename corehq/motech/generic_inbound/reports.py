from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.toggles import GENERIC_INBOUND_API


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
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Foo")),
            DataTablesColumn(_("Bar")),
        )

    @property
    def rows(self):
        return []
