from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from hsph.reports.field_management import HSPHSiteDataMixin

class HSPHCallCenterReport(StandardTabularHQReport, StandardDateHQReport):
    fields = ['corehq.apps.reports.fields.DatespanField']


class DCCActivityReport(HSPHCallCenterReport):
    name = "DCC Activity Report"
    slug = "hsph_dcc_activity"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCCField']

    def get_headers(self):
        return ["Name of DCC",
                "Total Number of Births Followed Up",
                "Number of births transferred to field for home visits",
                "Number of follow up calls where no data could be recorded",
                "Number of working days",
                "Total time for follow up",
                "Average time per follow up call"]


class CallCenterFollowUpSummaryReport(HSPHCallCenterReport, HSPHSiteDataMixin):
    name = "Call Center Follow Up Summary"
    slug = "hsph_dcc_followup_summary"

    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    def get_parameters(self):
        self.generate_sitemap()

    def get_headers(self):
        return ["Region",
                "District",
                "Site",
                "Total Number of Birth events with contact details",
                "Total number of births followed up",
                "Number of cases followed up at day 8th",
                "Number of cases followed up between day 9th to 13th",
                "Number of cases with contact details open at day 14th",
                "Number of cases with contact details transferred to Field management for home Visits",
                "Number of cases where no out comes could be recorded"]