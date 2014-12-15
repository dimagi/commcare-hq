from django.utils.translation import ugettext as _

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports import validate_report_parameters, get_location_hierarchy_by_id
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import ProjectIndicatorsCaseSqlData


class ProjectIndicatorsReport(MonthYearMixin, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Project Indicators Report"
    slug = "project_indicators_report"
    default_rows = 25
    base_template = "m4change/report.html"
    report_template_path = "m4change/report_content.html"

    fields = [
        AsyncLocationFilter,
        MonthFilter,
        YearFilter
    ]

    @classmethod
    def get_report_data(cls, config):
        validate_report_parameters(["domain", "location_id", "datespan"], config)

        domain = config["domain"]
        location_id = config["location_id"]
        sql_data = ProjectIndicatorsCaseSqlData(domain=domain, datespan=config["datespan"]).data
        locations = get_location_hierarchy_by_id(location_id, domain, CCT_only=True)
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
        return sorted([(key, row_data[key]) for key in row_data], key=lambda t: t[1].get("s/n"))

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
            },
            "number_of_free_sims_given_total": {
                "s/n": 33,
                "label": _("Number of free sim cards given"),
                "value": 0
            },
            "mno_mtn_total": {
                "s/n": 34,
                "label": _("Number of MTN MNO"),
                "value": 0
            },
            "mno_etisalat_total": {
                "s/n": 35,
                "label": _("Number of Etisalat MNO"),
                "value": 0
            },
            "mno_glo_total": {
                "s/n": 36,
                "label": _("Number of GLO MNO"),
                "value": 0
            },
            "mno_airtel_total": {
                "s/n": 37,
                "label": _("Number of Airtel MNO"),
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

        for row in row_data:
            yield [
                self.table_cell(row[1].get("s/n", "")),
                self.table_cell(row[1].get("label", "")),
                self.table_cell(row[1].get("value", 0))
            ]

    @property
    def rendered_report_title(self):
        return self.name

