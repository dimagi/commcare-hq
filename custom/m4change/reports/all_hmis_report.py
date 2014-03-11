from django.utils.translation import ugettext as _

from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, NumericColumn
from corehq.apps.reports.fields import AsyncLocationField
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports import validate_report_parameters
from custom.m4change.reports.anc_hmis_report import AncHmisReport
from custom.m4change.reports.immunization_hmis_report import ImmunizationHmisReport
from custom.m4change.reports.ld_hmis_report import LdHmisReport
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import AncHmisCaseSqlData, ImmunizationHmisCaseSqlData, LdHmisCaseSqlData


def _get_row(row_data, form_data, key):
    data = form_data.get(key)
    rows = dict([(row_key, data.get(row_key, 0)) for row_key in row_data])
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
    rows["antenatal_first_visit_total"] = rows.get("attendance_before_20_weeks_total") \
                                          + rows.get("attendance_after_20_weeks_total")
    return rows


class AllHmisReport(MonthYearMixin, CustomProjectReport, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Facility ALL HMIS Report"
    slug = "facility_all_hmis_report"
    default_rows = 25

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
        datespan = config["datespan"]
        sql_data = dict(
            AncHmisCaseSqlData(domain=domain, datespan=datespan).data.items() +\
            LdHmisCaseSqlData(domain=domain, datespan=datespan).data.items() +\
            ImmunizationHmisCaseSqlData(domain=domain, datespan=datespan).data.items()
        )
        top_location = Location.get(location_id)
        locations = [location_id] + [descendant.get_id for descendant in top_location.descendants]
        row_data = AllHmisReport.get_initial_row_data()

        for location_id in locations:
            key = (domain, location_id)
            if key in sql_data:
                report_rows = _get_row(row_data, sql_data, key)
                for key in report_rows:
                    row_data.get(key)["value"] += report_rows.get(key)
        return row_data


    @classmethod
    def get_initial_row_data(cls):
        return dict(
            AncHmisReport.get_initial_row_data().items() +\
            LdHmisReport.get_initial_row_data().items() +\
            ImmunizationHmisReport.get_initial_row_data().items()
        )

    @property
    def headers(self):
        headers = DataTablesHeader(NumericColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   NumericColumn(_("Total")))
        return headers

    @property
    def rows(self):
        row_data = AllHmisReport.get_report_data({
            "location_id": self.request.GET.get("location_id", None),
            "datespan": self.datespan,
            "domain": str(self.domain)
        })

        for key in row_data:
            yield [
                self.table_cell(row_data.get(key).get("hmis_code")),
                self.table_cell(row_data.get(key).get("label")),
                self.table_cell(row_data.get(key).get("value"))
            ]

    @property
    def rendered_report_title(self):
        return self.name
