from django.utils.translation import ugettext as _

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, NumericColumn
from corehq.apps.reports.fields import AsyncLocationField
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports import validate_report_parameters, get_location_hierarchy_by_id
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import McctMonthlyAggregateFormSqlData


def _get_rows(row_data, form_data, key):
    data = form_data.get(key)
    rows = dict([(row_key, data.get(row_key, 0)) for row_key in row_data])
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
    rows["all_eligible_clients_total"] += \
        rows["eligible_due_to_registration_total"] + \
        rows["eligible_due_to_4th_visit_total"] + \
        rows["eligible_due_to_delivery_total"] + \
        rows["eligible_due_to_immun_or_pnc_visit_total"]
    rows["all_reviewed_clients_total"] += \
        rows["status_reviewed_due_to_registration"] + \
        rows["status_reviewed_due_to_4th_visit"] + \
        rows["status_reviewed_due_to_delivery"] + \
        rows["status_reviewed_due_to_immun_or_pnc_visit"]
    rows["all_approved_clients_total"] += \
        rows["status_approved_due_to_registration"] + \
        rows["status_approved_due_to_4th_visit"] + \
        rows["status_approved_due_to_delivery"] + \
        rows["status_approved_due_to_immun_or_pnc_visit"]
    rows["all_rejected_clients_total"] += \
        rows["status_rejected_due_to_incorrect_phone_number"] + \
        rows["status_rejected_due_to_double_entry"] + \
        rows["status_rejected_due_to_other_errors"]
    rows["all_paid_clients_total"] += \
        rows["status_paid_due_to_registration"] + \
        rows["status_paid_due_to_4th_visit"] + \
        rows["status_paid_due_to_delivery"] + \
        rows["status_paid_due_to_immun_or_pnc_visit"]
    rows["all_clients_status_view_total"] += \
        rows["all_eligible_clients_total"] + \
        rows["all_reviewed_clients_total"] + \
        rows["all_approved_clients_total"] + \
        rows["all_rejected_clients_total"] + \
        rows["all_paid_clients_total"]

    return rows


class McctMonthlyAggregateReport(MonthYearMixin, CustomProjectReport, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "mCCT Monthly Aggregate Report"
    slug = "mcct_monthly_aggregate_report"
    default_rows = 50

    fields = [
        AsyncLocationField,
        MonthFilter,
        YearFilter
    ]

    @classmethod
    def get_report_data(cls, config):
        validate_report_parameters(["domain", "location_id", "datespan"], config)

        domain = config["domain"]
        location_id = config["location_id"]
        sql_data = McctMonthlyAggregateFormSqlData(domain=domain, datespan=config["datespan"]).data
        locations = get_location_hierarchy_by_id(location_id, domain)
        row_data = McctMonthlyAggregateReport.get_initial_row_data()

        for location_id in locations:
            key = (domain, location_id)
            if key in sql_data:
                report_rows = _get_rows(row_data, sql_data, key)
                for key in report_rows:
                    row_data.get(key)["value"] += report_rows.get(key)
        return row_data


    @classmethod
    def get_initial_row_data(self):
        return {
            "all_eligible_clients_total": {
                "s/n": 1, "label": _("All eligible clients"), "value": 0
            },
            "all_reviewed_clients_total": {
                "s/n": 2, "label": _("All reviewed clients"), "value": 0
            },
            "all_approved_clients_total": {
                "s/n": 3, "label": _("All approved clients"), "value": 0
            },
            "all_rejected_clients_total": {
                "s/n": 4, "label": _("All rejected clients"), "value": 0
            },
            "all_paid_clients_total": {
                "s/n": 5, "label": _("Paid clients for the month"), "value": 0
            },
            "eligible_due_to_registration_total": {
                "s/n": 6, "label": _("Eligible clients due to registration"), "value": 0
            },
            "eligible_due_to_4th_visit_total": {
                "s/n": 7, "label": _("Eligible clients due to 4th visit"), "value": 0
            },
            "eligible_due_to_delivery_total": {
                "s/n": 8, "label": _("Eligible clients due to delivery"), "value": 0
            },
            "eligible_due_to_immun_or_pnc_visit_total": {
                "s/n": 9, "label": _("Eligible clients due to immunization or PNC visit"), "value": 0
            },
            "status_reviewed_due_to_registration": {
                "s/n": 10, "label": _("Reviewed clients due to registration"), "value": 0
            },
            "status_reviewed_due_to_4th_visit": {
                "s/n": 11, "label": _("Reviewed clients due to 4th visit"), "value": 0
            },
            "status_reviewed_due_to_delivery": {
                "s/n": 12, "label": _("Reviewed clients due to delivery"), "value": 0
            },
            "status_reviewed_due_to_immun_or_pnc_visit": {
                "s/n": 13, "label": _("Reviewed clients due to immunization or PNC visit"), "value": 0
            },
            "status_approved_due_to_registration": {
                "s/n": 14, "label": _("Approved clients due to registration"), "value": 0
            },
            "status_approved_due_to_4th_visit": {
                "s/n": 15, "label": _("Approved clients due to 4th visit"), "value": 0
            },
            "status_approved_due_to_delivery": {
                "s/n": 16, "label": _("Approved clients due to delivery"), "value": 0
            },
            "status_approved_due_to_immun_or_pnc_visit": {
                "s/n": 17, "label": _("Approved clients due to immunization or PNC visit"), "value": 0
            },
            "status_paid_due_to_registration": {
                "s/n": 18, "label": _("Paid clients due to registration"), "value": 0
            },
            "status_paid_due_to_4th_visit": {
                "s/n": 19, "label": _("Paid clients due to 4th visit"), "value": 0
            },
            "status_paid_due_to_delivery": {
                "s/n": 20, "label": _("Paid clients due to delivery"), "value": 0
            },
            "status_paid_due_to_immun_or_pnc_visit": {
                "s/n": 21, "label": _("Paid clients due to immunization or PNC visit"), "value": 0
            },
            "status_rejected_due_to_incorrect_phone_number": {
                "s/n": 22, "label": _("Rejected clients due to incorrect phone number"), "value": 0
            },
            "status_rejected_due_to_double_entry": {
                "s/n": 23, "label": _("Rejected clients due to double entry"), "value": 0
            },
            "status_rejected_due_to_other_errors": {
                "s/n": 24, "label": _("Rejected clients due to other errors"), "value": 0
            },
            "all_clients_status_view_total": {
                "s/n": 26, "label": _("All clients status view"), "value": 0
            },
        }

    @property
    def headers(self):
        headers = DataTablesHeader(NumericColumn(_("s/n")),
                                   DataTablesColumn(_("Summary item")),
                                   NumericColumn(_("Total")))
        return headers

    @property
    def rows(self):
        row_data = McctMonthlyAggregateReport.get_report_data({
            "location_id": self.request.GET.get("location_id", None),
            "datespan": self.datespan,
            "domain": str(self.domain)
        })

        for key in row_data:
            yield [
                self.table_cell(row_data.get(key).get("s/n")),
                self.table_cell(row_data.get(key).get("label")),
                self.table_cell(row_data.get(key).get("value"))
            ]

    @property
    def rendered_report_title(self):
        return self.name
