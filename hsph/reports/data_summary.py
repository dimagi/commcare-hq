from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from hsph.reports.field_management import HSPHSiteDataMixin

class ProgramDataSummaryReport(StandardTabularHQReport, StandardDateHQReport, HSPHSiteDataMixin):
    name = "Program Data Summary"
    slug = "hsph_program_summary"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    def get_parameters(self):
        self.generate_sitemap()

    def get_headers(self):
        return ["Region",
                "District",
                "Site",
                "No. Births Recorded",
                "Maternal Deaths",
                "Maternal Near Miss",
                "Still Births",
                "Neonatal Mortality",
                "Maternal Deaths",
                "Maternal Near Miss",
                "Still Births",
                "Neonatal Mortality",
                "Maternal Deaths",
                "Maternal Near Miss",
                "Still Births",
                "Neonatal Mortality",
                "Total Primary Outcome Positive",
                "Total Negative Outcomes",
                "Lost to Follow Up"]


class ComparativeDataSummaryReport(StandardDateHQReport):
    name = "Comparative Data Summary Report"
    slug = "hsph_comparative_data_summary"
    fields = ['corehq.apps.reports.fields.DatespanField']