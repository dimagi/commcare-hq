from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport

class DCOActivityReport(StandardTabularHQReport, StandardDateHQReport):
    name = "DCO Activity Report"
    slug = "hsph_dco_activity"
    fields = ['corehq.apps.reports.fields.DatespanField']

    def get_headers(self):
        return ["Name of DCO",
                "Name of DCTL",
                "No. of Facility Visits",
                "No. of Facility Visits with less than 2 visits/week",
                "No. of Births Recorded",
                "Average time per Birth Record (min)",
                "No. of Home Visits assigned",
                "No. of Home Visits completed",
                "No. of Home Visits open at 21 days"]

    def get_rows(self):
        rows = []
        return rows

class DCOFieldDataCollectionActivityReport(StandardTabularHQReport, StandardDateHQReport):
    name = "DCO Field Data Collection Activity Report"
    slug = "hsph_dco_field_data"
    fields = ['corehq.apps.reports.fields.DatespanField']

    def get_headers(self):
        return ["Facility Name",
                "Name of DCO",
                "Name of DCTL",
                "No. of visits by DCO",
                "No. of births recorded",
                "No. of patients without contact details"]

    def get_rows(self):
        rows = []
        return rows