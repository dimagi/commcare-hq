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

        data = form_sql_data.data[DOMAIN]

        report_rows = [
            (23, _("Number of pregnant women who registered for ANC (in CCT payment sites only"), data.get("pregnant_mothers_registered_anc_total", 0)),
            (26, _("Number of women who had 4 ANC visits (in CCT payment sites only)"), data.get("women_having_4_anc_visits_total", 0)),
            (32, _("Number of women who attended PNC within 6 weeks of delivery"), data.get("women_delivering_within_6_weeks_attending_pnc_total", 0)),
        ]

        for row in report_rows:
            value = row[2]
            if value is None:
                value = 0
            yield [row[0], row[1], value]

    @property
    def rendered_report_title(self):
        return self.name

