from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import AsyncLocationField
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports.sql_data import AncHmisCaseSqlData
from custom.m4change.constants import DOMAIN


def __get_row__(row_data, form_data, key):
    data = form_data.get(key)
    rows = {key: data.get(key, 0) for key in row_data}
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
    rows["antenatal_first_visit_total"] = rows.get("attendance_before_20_weeks_total") \
                                          + rows.get("attendance_after_20_weeks_total")
    return rows

class AncHmisReport(MonthYearMixin, CustomProjectReport, CaseListReport, ReportDataSource):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Facility ANC HMIS Report"
    slug = "facility_anc_hmis_report"
    default_rows = 25

    fields = [
        AsyncLocationField,
        MonthFilter,
        YearFilter
    ]

    def __get_initial_row_data__(self):
        return {
            "attendance_total": {
                "hmis_code": "03", "label": _("Antenatal Attendance - Total"), "value": 0
            },
            "attendance_before_20_weeks_total": {
                "hmis_code": "04", "label": _("Antenatal first Visit before 20wks"), "value": 0
            },
            "attendance_after_20_weeks_total": {
                "hmis_code": "05", "label": _("Antenatal first Visit after 20wks"), "value": 0
            },
            "antenatal_first_visit_total": {
                "hmis_code": "06", "label": _("Antenatal first visit - total"), "value": 0
            },
            "attendance_gte_4_visits_total": {
                "hmis_code": "07", "label": _("Pregnant women that attend antenatal clinic for 4th visit during the month"), "value": 0
            },
            'anc_syphilis_test_done_total': {
                "hmis_code": "08", "label": _("ANC syphilis test done"), "value": 0
            },
            'anc_syphilis_test_positive_total': {
                "hmis_code": "09", "label": _("ANC syphilis test positive"), "value": 0
            },
            'anc_syphilis_case_treated_total': {
                "hmis_code": "10", "label": _("ANC syphilis case treated"), "value": 0
            },
            'pregnant_mothers_receiving_ipt1_total': {
                "hmis_code": "11", "label": _("Pregnant women who receive malaria IPT1"), "value": 0
            },
            'pregnant_mothers_receiving_ipt2_total': {
                "hmis_code": "12", "label": _("Pregnant women who receive malaria IPT2"), "value": 0
            },
            'pregnant_mothers_receiving_llin_total': {
                "hmis_code": "13", "label": _("Pregnant women who receive malaria LLIN"), "value": 0
            },
            'pregnant_mothers_receiving_ifa_total': {
                "hmis_code": "14", "label": _("Pregnant women who receive malaria Haematinics"), "value": 0
            },
            'postnatal_attendance_total': {
                "hmis_code": "15", "label": _("Postnatal Attendance - Total"), "value": 0
            },
            'postnatal_clinic_visit_lte_1_day_total': {
                "hmis_code": "16", "label": _("Postnatal clinic visit within 1 day of delivery"), "value": 0
            },
            'postnatal_clinic_visit_lte_3_days_total': {
                "hmis_code": "17", "label": _("Postnatal clinic visit within 3 days of delivery"), "value": 0
            },
            'postnatal_clinic_visit_gte_7_days_total': {
                "hmis_code": "18", "label": _("Postnatal clinic visit >= 7 days of delivery"), "value": 0
            }
        }

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   DataTablesColumn(_("Total")))
        return headers

    @property
    def rows(self):
        location_id = self.request.GET.get('location_id', None)
        self.form_sql_data = AncHmisCaseSqlData(domain=DOMAIN,
                                                datespan=self.datespan)
        form_data = self.form_sql_data.data
        top_location = Location.get(location_id)
        locations = [top_location.get_id] + [descendant.get_id for descendant in top_location.descendants]
        row_data = self.__get_initial_row_data__()

        for location_id in locations:
            key = (DOMAIN, location_id)
            if key in self.form_sql_data.data:
                report_rows = __get_row__(row_data, form_data, key)
                for key in report_rows:
                    row_data.get(key)["value"] += report_rows.get(key)

        for key in row_data:
            yield [
                row_data.get(key).get("hmis_code"),
                row_data.get(key).get("label"),
                row_data.get(key).get("value")
            ]


    @property
    @memoized
    def rendered_report_title(self):
        return self.name
