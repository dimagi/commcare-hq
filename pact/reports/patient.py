from corehq.apps.hqcase.paginator import CasePaginator
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import SelectMobileWorkerField
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.inspect import CaseListReport, CaseDisplay, CaseListMixin

from couchdbkit.resource import RequestFailed
from dimagi.utils.decorators.memoized import memoized



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
    name = "Patient List"
    slug = "pactpatient_list"
    hide_filters = True

#    asynchronous = False
    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("PACT ID"),
            DataTablesColumn("Name"),
            DataTablesColumn("Primary HP"),
            DataTablesColumn("Opened Date"),
            DataTablesColumn("Last Encounter"),
            DataTablesColumn("Encounter Date"),
            DataTablesColumn("HP Status"),
            DataTablesColumn("DOT Status"),
            DataTablesColumn("Last BW"),
            DataTablesColumn("Submissions"),
        )
#        headers.no_sort = True
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
                display.case_link,
                display.owner_display, #primary hp
                display.opened_on,
                "some encounter",
                display.modified_on,
                display.hp_status,
                display.dot_status,
                display.closed_display,
                "last bw",
                display.num_submissions,

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
    def pact_id(self):
        return self.case.external_id

    @property
    def hp_status(self):
        if hasattr(self.case, 'hp_status'):
            return self.case.hp_status
        else:
            return "no status"

    @property
    def dot_status(self):
        if hasattr(self.case, 'dot_status'):
            return self.case.dot_status
        else:
            return "no status"

    @property
    def num_submissions(self):
        return len(self.case.actions)
