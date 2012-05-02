from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from hsph.reports.field_management import HSPHSiteDataMixin

class ProjectStatusDashboardReport(StandardDateHQReport, HSPHSiteDataMixin):
    name = "Project Status Dashboard"
    slug = "hsph_project_status"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    def get_parameters(self):
        self.generate_sitemap()

class ImplementationStatusDashboardReport(StandardTabularHQReport, StandardDateHQReport, HSPHSiteDataMixin):
    name = "Implementation Status Dashboard"
    slug = "hsph_implementation_status"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    def get_parameters(self):
        self.generate_sitemap()

    def get_headers(self):
        return ["Status",
                "Region",
                "District",
                "IHF/CHF",
                "CITL Name",
                "Site",
                "Facility Status",
                "Status last updated on"]