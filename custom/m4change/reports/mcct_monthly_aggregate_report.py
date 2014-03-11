from django.utils.translation import ugettext as _

from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, NumericColumn
from corehq.apps.reports.fields import AsyncLocationField
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports import validate_report_parameters
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import McctMonthlyAggregateFormSqlData


def _get_row(row_data, form_data, key):
    data = form_data.get(key)
    rows = dict([(row_key, data.get(row_key, 0)) for row_key in row_data])
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
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
        top_location = Location.get(location_id)
        locations = [top_location.get_id] + [descendant.get_id for descendant in top_location.descendants]
        row_data = McctMonthlyAggregateReport.get_initial_row_data()

        for location_id in locations:
            key = (domain, location_id)
            if key in sql_data:
                report_rows = _get_row(row_data, sql_data, key)
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
            "paid_clients_for_the_month_total": {
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
            "reviewed_due_to_registration_total": {
                "s/n": 10, "label": _("Reviewed clients due to registration"), "value": 0
            },
            "reviewed_due_to_4th_visit_total": {
                "s/n": 11, "label": _("Reviewed clients due to 4th visit"), "value": 0
            },
            "reviewed_due_to_delivery_total": {
                "s/n": 12, "label": _("Reviewed clients due to delivery"), "value": 0
            },
            "reviewed_due_to_immun_or_pnc_visit_total": {
                "s/n": 13, "label": _("Reviewed clients due to immunization or PNC visit"), "value": 0
            },
            "approved_due_to_registration_total": {
                "s/n": 14, "label": _("Approved clients due to registration"), "value": 0
            },
            "approved_due_to_4th_visit_total": {
                "s/n": 15, "label": _("Approved clients due to 4th visit"), "value": 0
            },
            "approved_due_to_delivery_total": {
                "s/n": 16, "label": _("Approved clients due to delivery"), "value": 0
            },
            "approved_due_to_immun_or_pnc_visit_total": {
                "s/n": 17, "label": _("Approved clients due to immunization or PNC visit"), "value": 0
            },
            "paid_due_to_registration_total": {
                "s/n": 18, "label": _("Paid clients due to registration"), "value": 0
            },
            "paid_due_to_4th_visit_total": {
                "s/n": 19, "label": _("Paid clients due to 4th visit"), "value": 0
            },
            "paid_due_to_delivery_total": {
                "s/n": 20, "label": _("Paid clients due to delivery"), "value": 0
            },
            "paid_due_to_immun_or_pnc_visit_total": {
                "s/n": 21, "label": _("Paid clients due to immunization or PNC visit"), "value": 0
            },
            "rejected_due_to_registration_total": {
                "s/n": 22, "label": _("Rejected clients due to registration"), "value": 0
            },
            "rejected_due_to_4th_visit_total": {
                "s/n": 23, "label": _("Rejected clients due to 4th visit"), "value": 0
            },
            "rejected_due_to_delivery_total": {
                "s/n": 24, "label": _("Rejected clients due to delivery"), "value": 0
            },
            "rejected_due_to_immun_or_pnc_visit_total": {
                "s/n": 25, "label": _("Rejected clients due to immunization or PNC visit"), "value": 0
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
