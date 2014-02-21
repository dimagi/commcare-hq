from django.core.urlresolvers import NoReverseMatch, reverse
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.api.es import ReportCaseES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.pillows.base import restore_property_dict
from django.utils import html


class PatientListReportDisplay(CaseDisplay):

    @property
    def edit_link(self):
        try:
            return html.mark_safe("<a class='ajax_dialog' href=''>Edit</a>")
        except NoReverseMatch:
            return "%s (bad ID format)"

    @property
    def case_detail_url(self):
        try:
            return reverse('case_details', args=[self.report.domain, self.case_id])
        except NoReverseMatch:
            return None

    @property
    def mrn(self):
        return self.case.create.mrn

    @property
    def randomization_date(self):
        return "randomization_date"

    @property
    def visit_name(self):
        return "visit_name"

    @property
    def target_Date(self):
        return "target_Date"

    @property
    def most_recent(self):
        return "most_recent"

    @property
    def discuss(self):
        return "discuss"

    @property
    def patient_info(self):
        return "patient_info"



class PatientListReport(CustomProjectReport, CaseListReport):

    fields = ['custom.succeed.fields.CareSite',
              'custom.succeed.fields.ResponsibleParty',
              'custom.succeed.fields.PatientStatus']

    @property
    @memoized
    def case_es(self):
        return ReportCaseES(self.domain)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Modify Schedule")),
            DataTablesColumn(_("Name"), prop_name="name.exact"),
            DataTablesColumn(_("MRN")),
            DataTablesColumn(_("Randomization Date")),
            DataTablesColumn(_("Visit Name")),
            DataTablesColumn(_("Target Date")),
            DataTablesColumn(_("Most Recent BP")),
            DataTablesColumn(_("Discuss at Huddle?")),
            DataTablesColumn(_("Last Patient Interaction")),

        )
        return headers

    @property
    def rows(self):
        case_displays = (PatientListReportDisplay(self, restore_property_dict(self.get_case(case)))
                         for case in self.es_results['hits'].get('hits', []))

        for disp in case_displays:
            yield [
                disp.edit_link,
                disp.case_link,
                disp.mrn,
                disp.randomization_date,
                disp.visit_name,
                disp.target_Date,
                disp.most_recent,
                disp.discuss,
                disp.patient_info
            ]