from __future__ import absolute_import
from django.utils.translation import ugettext as _

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, NumericColumn
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.common.filters import RestrictedAsyncLocationFilter
from custom.m4change.reports import validate_report_parameters, get_location_hierarchy_by_id
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import AncHmisCaseSqlData


def _get_row(row_data, form_data, key):
    data = form_data.get(key)
    rows = dict([(row_key, data.get(row_key, 0)) for row_key in row_data])
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
    rows["antenatal_first_visit_total"] = rows.get("attendance_before_20_weeks_total") \
                                          + rows.get("attendance_after_20_weeks_total")
    return rows


@location_safe
class AncHmisReport(MonthYearMixin, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Facility ANC HMIS Report"
    slug = "facility_anc_hmis_report"
    default_rows = 25
    base_template = "m4change/report.html"
    report_template_path = "m4change/anc_hmis_report_content.html"

    fields = [
        RestrictedAsyncLocationFilter,
        MonthFilter,
        YearFilter
    ]

    @classmethod
    def get_report_data(cls, config):
        validate_report_parameters(["domain", "location_id", "datespan"], config)

        domain = config["domain"]
        location_id = config["location_id"]
        user = config["user"]

        sql_data = AncHmisCaseSqlData(domain=domain, datespan=config["datespan"]).data
        locations = get_location_hierarchy_by_id(location_id, domain, user)
        row_data = AncHmisReport.get_initial_row_data()

        for location_id in locations:
            key = (domain, location_id)
            if key in sql_data:
                report_rows = _get_row(row_data, sql_data, key)
                for key in report_rows:
                    row_data.get(key)["value"] += report_rows.get(key)
        return sorted([(key, row_data[key]) for key in row_data], key=lambda t: t[1].get("hmis_code"))

    @classmethod
    def get_initial_row_data(cls):
        return {
            "attendance_total": {
                "hmis_code": 3, "label": _("Antenatal Attendance - Total"), "value": 0
            },
            "attendance_before_20_weeks_total": {
                "hmis_code": 4, "label": _("Antenatal first Visit before 20wks"), "value": 0
            },
            "attendance_after_20_weeks_total": {
                "hmis_code": 5, "label": _("Antenatal first Visit after 20wks"), "value": 0
            },
            "antenatal_first_visit_total": {
                "hmis_code": 6, "label": _("Antenatal first visit - total"), "value": 0
            },
            "attendance_gte_4_visits_total": {
                "hmis_code": 7, "label": _("Pregnant women that attend antenatal clinic for 4th visit during the month"), "value": 0
            },
            'anc_syphilis_test_done_total': {
                "hmis_code": 8, "label": _("ANC syphilis test done"), "value": 0
            },
            'anc_syphilis_test_positive_total': {
                "hmis_code": 9, "label": _("ANC syphilis test positive"), "value": 0
            },
            'anc_syphilis_case_treated_total': {
                "hmis_code": 10, "label": _("ANC syphilis case treated"), "value": 0
            },
            'pregnant_mothers_receiving_ipt1_total': {
                "hmis_code": 11, "label": _("Pregnant women who receive malaria IPT1"), "value": 0
            },
            'pregnant_mothers_receiving_ipt2_total': {
                "hmis_code": 12, "label": _("Pregnant women who receive malaria IPT2"), "value": 0
            },
            'pregnant_mothers_receiving_llin_total': {
                "hmis_code": 13, "label": _("Pregnant women who receive malaria LLIN"), "value": 0
            },
            'pregnant_mothers_receiving_ifa_total': {
                "hmis_code": 14, "label": _("Pregnant women who receive malaria Haematinics"), "value": 0
            },
            'postnatal_attendance_total': {
                "hmis_code": 15, "label": _("Postnatal Attendance - Total"), "value": 0
            },
            'postnatal_clinic_visit_lte_1_day_total': {
                "hmis_code": 16, "label": _("Postnatal clinic visit within 1 day of delivery"), "value": 0
            },
            'postnatal_clinic_visit_lte_3_days_total': {
                "hmis_code": 17, "label": _("Postnatal clinic visit within 3 days of delivery"), "value": 0
            },
            'postnatal_clinic_visit_gte_7_days_total': {
                "hmis_code": 18, "label": _("Postnatal clinic visit >= 7 days of delivery"), "value": 0
            }
        }

    @property
    def headers(self):
        headers = DataTablesHeader(NumericColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   NumericColumn(_("Total")))
        return headers

    @property
    def rows(self):
        row_data = AncHmisReport.get_report_data({
            "location_id": self.request.GET.get("location_id", None),
            "datespan": self.datespan,
            "domain": str(self.domain),
            "user": self.request.couch_user
        })

        for row in row_data:
            yield [
                self.table_cell(row[1].get("hmis_code")),
                self.table_cell(row[1].get("label")),
                self.table_cell(row[1].get("value"))
            ]

    @property
    def rendered_report_title(self):
        return self.name
