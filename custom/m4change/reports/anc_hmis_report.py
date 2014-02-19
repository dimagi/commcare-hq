from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports.sql_data import AncHmisCaseSqlData
from custom.m4change.constants import DOMAIN

class AncHmisReport(MonthYearMixin, CustomProjectReport, CaseListReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Facility ANC HMIS Report"
    slug = "facility_anc_hmis_report"
    base_template = "reports/report.html"
    default_rows = 25

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   DataTablesColumn(_("Total")))
        return headers

    @property
    def rows(self):
        self.form_sql_data = AncHmisCaseSqlData(domain=DOMAIN, datespan=self.datespan)
        antenatal_first_visit_total = self.form_sql_data.data[DOMAIN].get("attendance_before_20_weeks_total", 0)\
                                      + self.form_sql_data.data[DOMAIN].get("attendance_after_20_weeks_total", 0)

        print(self.form_sql_data.data[DOMAIN])

        report_rows = [
            (3, _("Antenatal Attendance - Total"), self.form_sql_data.data[DOMAIN].get("attendance_total", 0)),
            (4, _("Antenatal first Visit before 20wks"), self.form_sql_data.data[DOMAIN].get("attendance_before_20_weeks_total", 0)),
            (5, _("Antenatal first Visit after 20wks"), self.form_sql_data.data[DOMAIN].get("attendance_after_20_weeks_total", 0)),
            (6, _("Antenatal first visit - total"), antenatal_first_visit_total),
            (7, _("Pregnant Women that attend antenatal clinic for 4th visit during the month"),
                self.form_sql_data.data[DOMAIN].get("attendance_gte_4_visits_total", 0)),
            (8, _("ANC syphilis test done"), self.form_sql_data.data[DOMAIN].get('anc_syphilis_test_done_total', 0)),
            (9, _("ANC syphilis test positive"), self.form_sql_data.data[DOMAIN].get('anc_syphilis_test_positive_total', 0)),
            (10, _("ANC syphilis case treated"), self.form_sql_data.data[DOMAIN].get('anc_syphilis_case_treated_total', 0)),
            (11, _("Pregnant women who receive malaria IPT1"), self.form_sql_data.data[DOMAIN].get('pregnant_mothers_receiving_ipt1_total', 0)),
            (12, _("Pregnant women who receive malaria IPT2"),self.form_sql_data.data[DOMAIN].get('pregnant_mothers_receiving_ipt2_total', 0)),
            (13, _("Pregnant women who receive LLIN"), self.form_sql_data.data[DOMAIN].get('pregnant_mothers_receiving_llin_total', 0)),
            (14, _("Pregnant women who receive Haematinics"), self.form_sql_data.data[DOMAIN].get('pregnant_mothers_receiving_ifa_total', 0)),
            (15, _("Postnatal Attendance - Total"), self.form_sql_data.data[DOMAIN].get('postnatal_attendance_total', 0)),
            (16, _("Postnatal clinic visit within 1 day of delivery"),
                self.form_sql_data.data[DOMAIN].get('postnatal_clinic_visit_lte_1_day_total', 0)),
            (17, _("Postnatal clinic visit within 3 days of delivery"),
                self.form_sql_data.data[DOMAIN].get('postnatal_clinic_visit_lte_3_days_total', 0)),
            (18, _("Postanatal clinic visit >= 7 days of delivery"),
                self.form_sql_data.data[DOMAIN].get('postnatal_clinic_visit_gte_7_days_total', 0))
        ]

        for row in report_rows:
            value = row[2]
            if value is None:
                value = 0
            yield [row[0], row[1], value]

    @property
    @memoized
    def rendered_report_title(self):
        return self.name
