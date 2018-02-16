from __future__ import absolute_import
from django.utils.translation import ugettext as _

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, NumericColumn
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.common.filters import RestrictedAsyncLocationFilter
from custom.m4change.filters import FacilityHmisFilter
from custom.m4change.reports.all_hmis_report import AllHmisReport
from custom.m4change.reports.anc_hmis_report import AncHmisReport
from custom.m4change.reports.immunization_hmis_report import ImmunizationHmisReport
from custom.m4change.reports.ld_hmis_report import LdHmisReport
from custom.m4change.reports.reports import M4ChangeReport


@location_safe
class AggregateFacilityWebHmisReport(MonthYearMixin, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Aggregate Facility Web HMIS Report"
    slug = "aggregate_facility_web_hmis_report"
    default_rows = 25
    base_template = "m4change/report.html"
    report_template_path = "m4change/report_content.html"

    fields = [
        RestrictedAsyncLocationFilter,
        MonthFilter,
        YearFilter,
        FacilityHmisFilter
    ]

    @property
    def headers(self):
        headers = DataTablesHeader(NumericColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   NumericColumn(_("Total")))
        return headers

    @property
    def rows(self):
        facility_hmis_filter = self.request.GET.get("facility_hmis_filter", "")
        row_data = {}
        report_map = {
            "all": AllHmisReport,
            "anc": AncHmisReport,
            "immunization": ImmunizationHmisReport,
            "ld": LdHmisReport
        }
        if facility_hmis_filter in report_map:
            row_data = report_map[facility_hmis_filter].get_report_data({
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
