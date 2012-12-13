from django.core.urlresolvers import reverse, NoReverseMatch
from corehq.apps.hqcase.paginator import CasePaginator
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import SelectMobileWorkerField
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.standard.inspect import CaseListReport, CaseDisplay, CaseListMixin
from django.utils import html

from couchdbkit.resource import RequestFailed
from dimagi.utils.decorators.memoized import memoized
from pact.reports.patient import PactPatientInfoReport


class PactCaseListMixin(CaseListMixin):

    @property
    @memoized
    def case_results(self):
        return CasePaginator(
            domain=self.domain,
            params=self.pagination,
            case_type=self.case_type,
            owner_ids=self.case_owners,
            user_ids=self.user_ids,
            status=self.case_status
        ).results()

    def CaseDisplay(self, case):
        return PactCaseDisplay(self, case)
    pass

class PatientDashboardReport(CaseListReport, PactCaseListMixin, CustomProjectReport):
    name = "All Patients"
    slug = "patients"
    hide_filters = True
#    ajax_pagination = True

    fields = [
#        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.SelectCaseOwnerField',
#        'corehq.apps.reports.fields.CaseTypeField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
    ]


#    asynchronous = False
    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("PACT ID"),
            DataTablesColumn("Name"),
            DataTablesColumn("Primary HP"),
            DataTablesColumn("Opened Date"),
            DataTablesColumn("Last Modified"),
            DataTablesColumn("HP Status"),
            DataTablesColumn("DOT Status"),
            DataTablesColumn("Status"),
        )
#        headers.no_sort = True
        headers.no_sort = False

        if not self.individual:
            self.name = "%s for %s" % (self.name, SelectMobileWorkerField.get_default_text(self.user_filter))

        return headers


    @property
    def rows(self):
        rows = []
        def _format_row(row):
            case = self.get_case(row)
            display = self.CaseDisplay(case)

            return [
                display.pact_id,
                display.pact_case_link,
                display.primary_hp, #primary hp
                display.opened_on,
                display.modified_on,
                display.hp_status,
                display.dot_status,
                display.closed_display,
            ]

        try:
            for item in self.case_results['rows']:
                row = _format_row(item)
                if row is not None:
                    rows.append(row)
        except RequestFailed:
            pass

        return rows


class PactCaseDisplay(CaseDisplay):
    @property
    def pact_case_link(self):
        case_id, case_name = self.case.case_id, self.case.name
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(PactPatientInfoReport.get_url(*[self.report.domain]) + "?patient_id=%s" % case_id),
                html.escape(case_name),
                ))
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name

    @property
    def pact_id(self):
        return self.case.external_id

    @property
    def hp_status(self):
        if hasattr(self.case, 'hp_status'):
            return self.case.hp_status
        else:
            return "no status"

    @property
    def primary_hp(self):
        if hasattr(self.case, 'hp'):
            return self.case.hp
        else:
            return "no HP"

    @property
    def dot_status(self):
        if hasattr(self.case, 'dot_status') and (self.case.dot_status != None and self.case.dot_status != ""):
            return self.case.dot_status
        else:
            return "---"

    @property
    def num_submissions(self):
        return len(self.case.actions)


