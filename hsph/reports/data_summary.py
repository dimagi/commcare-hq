from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup, DataTablesHeader
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

        region = DataTablesColumn("Region")
        district = DataTablesColumn("District")
        site = DataTablesColumn("Site")
        num_births = DataTablesColumn("No. Births Recorded")

        maternal_deaths = DataTablesColumn("Maternal Deaths")
        maternal_near_miss = DataTablesColumn("Maternal Near Miss")
        still_births = DataTablesColumn("Still Births")
        neonatal_mortality = DataTablesColumn("Neonatal Mortality")

        outcomes_on_discharge = DataTablesColumnGroup("Outcomes on Discharge",
            maternal_deaths,
            maternal_near_miss,
            still_births,
            neonatal_mortality)
        outcomes_on_discharge.css_span = 2

        outcomes_on_7days = DataTablesColumnGroup("Outcomes on 7 Days",
            maternal_deaths,
            maternal_near_miss,
            still_births,
            neonatal_mortality)
        outcomes_on_7days.css_span = 2

        positive_outcomes = DataTablesColumnGroup("Total Positive Outcomes",
            maternal_deaths,
            maternal_near_miss,
            still_births,
            neonatal_mortality)
        positive_outcomes.css_span = 2


        primary_outcome = DataTablesColumn("Primary Outcome Positive")
        negative_outcome = DataTablesColumn("Total Negative Outcomes")
        lost = DataTablesColumn("Lost to Followup")

        return DataTablesHeader(region,
            district,
            site,
            num_births,
            outcomes_on_discharge,
            outcomes_on_7days,
            positive_outcomes,
            primary_outcome,
            negative_outcome,
            lost)

    def get_rows(self):
        rows = []
        return rows


class ComparativeDataSummaryReport(StandardDateHQReport):
    name = "Comparative Data Summary Report"
    slug = "hsph_comparative_data_summary"
    fields = ['corehq.apps.reports.fields.DatespanField']