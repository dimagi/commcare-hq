from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import AsyncLocationField
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import MonthYearMixin, CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import ProjectIndicatorsCaseSqlData


class ProjectIndicatorsReport(MonthYearMixin, CustomProjectReport, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Project Indicators Report"
    slug = "project_indicators_report"
    default_rows = 25

    fields = [
        AsyncLocationField,
        MonthFilter,
        YearFilter
    ]

    @classmethod
    def get_report_data(cls, config):
        if "location_id" not in config:
            raise KeyError(_("Parameter 'location_id' is missing"))
        if "datespan" not in config:
            raise KeyError(_("Parameter 'datespan' is missing"))
        if "domain" not in config:
            raise KeyError(_("Parameter 'domain' is missing"))

        domain = config.get("domain", None)
        location_id = config.get("location_id", None)
        sql_data = ProjectIndicatorsCaseSqlData(domain=domain, datespan=config.get("datespan", None)).data
        top_location = Location.get(location_id)
        locations = [location_id] + [descendant.get_id for descendant in top_location.descendants]
        row_data = ProjectIndicatorsReport.get_initial_row_data()

        for key in sql_data:
            if key[2] not in locations:
                continue
            data = sql_data.get(key, {})
            for row_key in row_data:
                value = data.get(row_key, 0)
                if value is None:
                    value = 0
                if row_key == "women_delivering_within_6_weeks_attending_pnc_total" and value > 1:
                    value = 1
                row_data.get(row_key, {})["value"] += value
        return row_data

    @classmethod
    def get_initial_row_data(cls):
        return {
            "women_registered_anc_total": {
                "s/n": 23,
                "label": _("Number of pregnant women who registered for ANC (in CCT payment sites only)"),
                "value": 0
            },
            "women_having_4_anc_visits_total": {
                "s/n": 26,
                "label": _("Number of women who had 4 ANC visits (in CCT payment sites only)"),
                "value": 0
            },
            "women_delivering_at_facility_cct_total": {
                "s/n": 29,
                "label": _("Number of women who delivered at the facility (in CCT payment sites only)"),
                "value": 0
            },
            "women_delivering_within_6_weeks_attending_pnc_total": {
                "s/n": 32,
                "label": _("Number of women who attended PNC within 6 weeks of delivery"),
                "value": 0
            }
        }

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("s/n")),
                                   DataTablesColumn(_("m4change Project Indicators")),
                                   DataTablesColumn(_("Total")))
        return headers

    @property
    def rows(self):
        row_data = ProjectIndicatorsReport.get_report_data({
            "location_id": self.request.GET.get("location_id", None),
            "datespan": self.datespan,
            "domain": str(self.domain)
        })

        for key in row_data:
            yield [
                self.table_cell(row_data.get(key).get("s/n", "")),
                self.table_cell(row_data.get(key).get("label", "")),
                self.table_cell(row_data.get(key).get("value", 0))
            ]

    @property
    def rendered_report_title(self):
        return self.name

