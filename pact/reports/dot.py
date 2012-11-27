from corehq.apps.hqcase.paginator import CasePaginator
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import SelectMobileWorkerField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.standard.inspect import CaseListReport, CaseDisplay, CaseListMixin

from couchdbkit.resource import RequestFailed
from dimagi.utils.decorators.memoized import memoized




class PactDOTReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    name = "DOT Patient List"
    slug = "pact_dots"

    description = "PACT DOT Report"
    report_template_path = "pact/dots/dots_report.html"
    hide_filters = True
    flush_layout = True
    fields=[]

    @property
    def report_context(self):
        return {'foo': 'bar', 'what': 'up'}
#        return dict(
#            reportdata=dict(
#                domain=self.domain,
#                patients=['a', 'b', 'c']
#            )
#        )


