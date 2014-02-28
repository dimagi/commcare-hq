from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import MonthYearMixin, CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.constants import DOMAIN
from custom.m4change.reports.sql_data import ProjectIndicatorsCaseSqlData


class ProjectIndicatorsReport(MonthYearMixin, CustomProjectReport, CaseListReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Project Indicators Report"
    slug = "facility_project_indicators_report"
    default_rows = 25

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("s/n")),
                                   DataTablesColumn(_("m4change Project Indicators")),
                                   DataTablesColumn(_("Total")))
        return headers

    @property
    def rows(self):
        form_sql_data = ProjectIndicatorsCaseSqlData(domain=DOMAIN, datespan=self.datespan)

        report_rows = {
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
        }

        sql_data = form_sql_data.data
        for key in sql_data:
            data = sql_data.get(key, {})
            for row_key in report_rows:
                value = data.get(row_key, 0)
                if value is None:
                    value = 0
                if row_key == 'women_delivering_within_6_weeks_attending_pnc_total' and value > 1:
                    value = 1
                report_rows.get(row_key, {})["value"] += value

        for row_key in report_rows:
            row = report_rows.get(row_key, {})
            yield [row.get("s/n"), row.get("label"), row.get("value")]

    @property
    def rendered_report_title(self):
        return self.name

