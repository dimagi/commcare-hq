from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from mvp_docs.models import IndicatorXForm


class VerbalAutopsyDeidentifiedReport(GenericTabularReport, CustomProjectReport):
    """
        MVP Custom Report: Deidentified Verbal Autopsy  Report
    """
    slug = "deidentifiedreport_va"
    name = "Deidentified Verbal Autopsy  Report"
    flush_layout = True
    fields = ['corehq.apps.reports.filters.select.MonthFilter',
              'corehq.apps.reports.filters.select.YearFilter']

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("#"),
            DataTablesColumn("Month of Death"),
            DataTablesColumn("Year of Death"),
            DataTablesColumn("Age at Death"),
            DataTablesColumn("Name of Affiliated Health Facility"),
            DataTablesColumn("Place of Death"),
            DataTablesColumn("Medical Probable Cause of Death"),
            DataTablesColumn("Reason for delay and/or not receiving medical care"),
            DataTablesColumn("Was any treatment received for the illness that let to death?"),
            DataTablesColumn("Who provided treatment?"),
            DataTablesColumn("Date of Last CHW Visit")
        )

    @property
    def rows(self):
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)

        db = IndicatorXForm.get_db()

        results = db.view('mvp_verbal_autopsy_indicators/all_va_forms_cases', key=[int(month), int(year)], include_docs=True).all()

        indicators = [
            "case_id",
            "death_month",
            "death_year",
            "age_category",
            "death_facility",
            "death_place",
            "medical_reason",
            "no_treatment_reason",
            "received_treatment",
            "treatment_provider",
            "last_chw_visit"
        ]

        rows = []
        for result in results:
            row = []
            for ind in indicators:
                if ind in result['value']:
                    row.append(result['value'][ind])
                else:
                    row.append('-')

            rows.append(row)

        return rows
