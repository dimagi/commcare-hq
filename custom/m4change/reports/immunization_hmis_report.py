from django.utils.translation import ugettext as _

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports import validate_report_parameters, get_location_hierarchy_by_id
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import ImmunizationHmisCaseSqlData


def _get_row(row_data, form_data, key):
    data = form_data.get(key)
    rows = dict([(row_key, data.get(row_key, 0)) for row_key in row_data])
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
    return rows


class ImmunizationHmisReport(MonthYearMixin, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Facility Immunization HMIS Report"
    slug = "facility_immunization_hmis_report"
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
        sql_data = ImmunizationHmisCaseSqlData(domain=domain, datespan=config["datespan"]).data
        locations = get_location_hierarchy_by_id(location_id, domain)
        row_data = ImmunizationHmisReport.get_initial_row_data()

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
            "opv_0_total": {
                "hmis_code": 47, "label": _("OPV0 - birth "), "value": 0
            },
            "hep_b_0_total": {
                "hmis_code": 48, "label": _("Hep.B0 - birth"), "value": 0 
            },
            "bcg_total": {
                "hmis_code": 49, "label": _("BCG"), "value": 0
            },
            "opv_1_total": {
                "hmis_code": 50, "label": _("OPV1"), "value": 0
            },
            "hep_b_1_total": {
                "hmis_code": 51, "label": _("HEP.B1"), "value": 0
            },
            "penta_1_total": {
                "hmis_code": 52, "label": _("Penta.1"), "value": 0
            },
            "dpt_1_total": {
                "hmis_code": 53, "label": _("DPT1 (not when using Penta)"), "value": 0
            },
            "pcv_1_total": {
                "hmis_code": 54, "label": _("PCV1"), "value": 0
            },
            "opv_2_total": {
                "hmis_code": 55, "label": _("OPV2"), "value": 0
            },
            "hep_b_2_total": {
                "hmis_code": 56, "label": _("Hep.B2"), "value": 0 
            },
            "penta_2_total": {
                "hmis_code": 57, "label": _("Penta.2"), "value": 0
            },
            "dpt_2_total": {
                "hmis_code": 58, "label": _("DPT2 (not when using Penta)"), "value": 0
            },
            "pcv_2_total": {
                "hmis_code": 59, "label": _("PCV2"), "value": 0 
            },
            "opv_3_total": {
                "hmis_code": 60, "label": _("OPV3"), "value": 0
            },
            "penta_3_total": {
                "hmis_code": 61, "label": _("Penta.3"), "value": 0 
            },
            "dpt_3_total": {
                "hmis_code": 62, "label": _("DPT3 (not when using Penta)"), "value": 0 
            },
            "pcv_3_total": { 
                "hmis_code": 63, "label": _("PCV3"), "value": 0 
            },
            "measles_1_total": {
                "hmis_code": 64, "label": _("Measles 1"), "value": 0 
            },
            "fully_immunized_total": {
                "hmis_code": 65, "label": _("Fully Immunized (<1 year)"), "value": 0 
            },
            "yellow_fever_total": {
                "hmis_code": 66, "label": _("Yellow Fever"), "value": 0 
            },
            "measles_2_total": {
                "hmis_code": 67, "label": _("Measles 2"), "value": 0 
            },
            "conjugate_csm_total": {
                "hmis_code": 68, "label": _("Conjugate A CSM"), "value": 0 
            },
        }

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   DataTablesColumn(_("Total")))
        return headers

    @property
    def rows(self):
        row_data = ImmunizationHmisReport.get_report_data({
            "location_id": self.request.GET.get("location_id", None),
            "datespan": self.datespan,
            "domain": str(self.domain)
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
