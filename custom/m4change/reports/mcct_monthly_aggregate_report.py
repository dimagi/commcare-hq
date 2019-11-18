from django.utils.translation import ugettext as _

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, NumericColumn
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.common.filters import RestrictedAsyncLocationFilter
from custom.m4change.constants import FOLLOW_UP_FORMS
from custom.m4change.models import McctStatus
from custom.m4change.reports import validate_report_parameters, get_location_hierarchy_by_id
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import McctMonthlyAggregateFormSqlData
from couchforms.models import XFormInstance


def _get_rows(row_data, form_data, key):
    data = form_data.get(key)
    rows = dict([(row_key, data.get(row_key, 0)) for row_key in row_data])
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
    rows["all_eligible_clients_total"] += \
        rows["status_eligible_due_to_registration"] + \
        rows["status_eligible_due_to_4th_visit"] + \
        rows["status_eligible_due_to_delivery"] + \
        rows["status_eligible_due_to_immun_or_pnc_visit"]
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


def _add_eligible_9months(row_data, start_date, end_date, domain):
    eligible_9months = McctStatus.objects\
        .filter(domain__exact=domain)\
        .filter(status__exact="eligible")\
        .filter(immunized=False)\
        .filter(is_booking=False)\
        .filter(received_on__range=(start_date, end_date))
    forms = [form for form in [XFormInstance.get(status.form_id) for status in eligible_9months]
             if form.xmlns in FOLLOW_UP_FORMS]
    forms_4th_visit = [form for form in forms if form.form.get("visits", "") == "4"]
    row_data["all_eligible_clients_total"]["value"] += len(forms) - len(forms_4th_visit)
    row_data["status_eligible_due_to_4th_visit"]["value"] += len(forms_4th_visit)


@location_safe
class McctMonthlyAggregateReport(MonthYearMixin, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "mCCT Monthly Aggregate Report"
    slug = "mcct_monthly_aggregate_report"
    default_rows = 50
    base_template = "m4change/report.html"
    report_template_path = "m4change/report_content.html"

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
        datespan = config["datespan"]
        user = config["user"]

        sql_data = McctMonthlyAggregateFormSqlData(domain=domain, datespan=datespan).data
        locations = get_location_hierarchy_by_id(location_id, domain, user, CCT_only=True)
        row_data = McctMonthlyAggregateReport.get_initial_row_data()

        for location_id in locations:
            key = (domain, location_id)
            if key in sql_data:
                report_rows = _get_rows(row_data, sql_data, key)
                for key in report_rows:
                    row_data.get(key)["value"] += report_rows.get(key)

        _add_eligible_9months(row_data, datespan.startdate_utc, datespan.enddate_utc, domain)
        return sorted([(key, row_data[key]) for key in row_data], key=lambda t: t[1].get("s/n"))

    @classmethod
    def get_initial_row_data(self):
        return {
            "all_eligible_clients_total": {
                "s/n": 1, "label": _("All eligible beneficiaries"), "value": 0
            },
            "all_reviewed_clients_total": {
                "s/n": 2, "label": _("All reviewed beneficiaries"), "value": 0
            },
            "all_approved_clients_total": {
                "s/n": 3, "label": _("All approved beneficiaries"), "value": 0
            },
            "all_rejected_clients_total": {
                "s/n": 4, "label": _("All rejected beneficiaries"), "value": 0
            },
            "all_paid_clients_total": {
                "s/n": 5, "label": _("Paid beneficiaries for the month"), "value": 0
            },
            "status_eligible_due_to_registration": {
                "s/n": 6, "label": _("Eligible beneficiaries due to registration"), "value": 0
            },
            "status_eligible_due_to_4th_visit": {
                "s/n": 7, "label": _("Eligible beneficiaries due to 4th visit"), "value": 0
            },
            "status_eligible_due_to_delivery": {
                "s/n": 8, "label": _("Eligible beneficiaries due to delivery"), "value": 0
            },
            "status_eligible_due_to_immun_or_pnc_visit": {
                "s/n": 9, "label": _("Eligible beneficiaries due to immunization or PNC visit"), "value": 0
            },
            "status_reviewed_due_to_registration": {
                "s/n": 10, "label": _("Reviewed beneficiaries due to registration"), "value": 0
            },
            "status_reviewed_due_to_4th_visit": {
                "s/n": 11, "label": _("Reviewed beneficiaries due to 4th visit"), "value": 0
            },
            "status_reviewed_due_to_delivery": {
                "s/n": 12, "label": _("Reviewed beneficiaries due to delivery"), "value": 0
            },
            "status_reviewed_due_to_immun_or_pnc_visit": {
                "s/n": 13, "label": _("Reviewed beneficiaries due to immunization or PNC visit"), "value": 0
            },
            "status_approved_due_to_registration": {
                "s/n": 14, "label": _("Approved beneficiaries due to registration"), "value": 0
            },
            "status_approved_due_to_4th_visit": {
                "s/n": 15, "label": _("Approved beneficiaries due to 4th visit"), "value": 0
            },
            "status_approved_due_to_delivery": {
                "s/n": 16, "label": _("Approved beneficiaries due to delivery"), "value": 0
            },
            "status_approved_due_to_immun_or_pnc_visit": {
                "s/n": 17, "label": _("Approved beneficiaries due to immunization or PNC visit"), "value": 0
            },
            "status_paid_due_to_registration": {
                "s/n": 18, "label": _("Paid beneficiaries due to registration"), "value": 0
            },
            "status_paid_due_to_4th_visit": {
                "s/n": 19, "label": _("Paid beneficiaries due to 4th visit"), "value": 0
            },
            "status_paid_due_to_delivery": {
                "s/n": 20, "label": _("Paid beneficiaries due to delivery"), "value": 0
            },
            "status_paid_due_to_immun_or_pnc_visit": {
                "s/n": 21, "label": _("Paid beneficiaries due to immunization or PNC visit"), "value": 0
            },
            "status_rejected_due_to_incorrect_phone_number": {
                "s/n": 22, "label": _("Rejected beneficiaries due to incorrect phone number"), "value": 0
            },
            "status_rejected_due_to_double_entry": {
                "s/n": 23, "label": _("Rejected beneficiaries due to double entry"), "value": 0
            },
            "status_rejected_due_to_other_errors": {
                "s/n": 24, "label": _("Rejected beneficiaries due to other errors"), "value": 0
            },
            "all_clients_status_view_total": {
                "s/n": 26, "label": _("All beneficiaries status view"), "value": 0
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
            "domain": str(self.domain),
            "user": self.request.couch_user
        })

        for row in row_data:
            yield [
                self.table_cell(row[1].get("s/n")),
                self.table_cell(row[1].get("label")),
                self.table_cell(row[1].get("value"))
            ]

    @property
    def rendered_report_title(self):
        return self.name
