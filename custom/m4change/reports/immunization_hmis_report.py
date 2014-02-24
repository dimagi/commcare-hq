from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.m4change.reports.sql_data import ImmunizationHmisCaseSqlData
from custom.m4change.constants import DOMAIN

class ImmunizationHmisReport(MonthYearMixin, CustomProjectReport, CaseListReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Facility Immunization HMIS Report"
    slug = "facility_immunization_hmis_report"
    default_rows = 25

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   DataTablesColumn(_("Total")))
        return headers

    @property
    def rows(self):
        self.form_sql_data = ImmunizationHmisCaseSqlData(domain=DOMAIN, datespan=self.datespan)

        print(self.form_sql_data.data[DOMAIN])
        data = self.form_sql_data.data[DOMAIN]

        report_rows = [
            (47, _("OPV0 - birth "), data.get("opv_0_total", 0)),
            (48, _("Hep.B0 - birth"), data.get("hep_b_0_total", 0)),
            (49, _("BCG"), data.get("bcg_total", 0)),
            (50, _("OPV1"), data.get("opv_1_total", 0)),
            (51, _("HEP.B1"), data.get("hep_b_1_total", 0)),
            (52, _("Penta.1"), data.get("penta_1_total", 0)),
            (53, _("DPT1 (not when using Penta)"), data.get("dpt_1_total", 0)),
            (54, _("PCV1"), data.get("pcv_1_total", 0)),
            (55, _("OPV2"), data.get("opv_2_total", 0)),
            (56, _("Hep.B2"), data.get("hep_b_2_total", 0)),
            (57, _("Penta.2"), data.get("penta_2_total", 0)),
            (58, _("DPT2 (not when using Penta)"), data.get("dpt_2_total", 0)),
            (59, _("PCV2"), data.get("pcv_2_total", 0)),
            (60, _("OPV3"), data.get("opv_3_total", 0)),
            (61, _("Penta.3"), data.get("penta_3", 0)),
            (62, _("DPT3 (not when using Penta)"), data.get("dpt_3_total", 0)),
            (63, _("PCV3"), data.get("pcv_3_total", 0)),
            (64, _("Measles 1"), data.get("measles_1_total", 0)),
            (65, _("Fully Immunized (<1year)"), data.get("fully_immunized_total", 0)),
            (66, _("Yellow Fever"), data.get("yellow_fever_total", 0)),
            (67, _("Measles 2"), data.get("measles_2_total", 0)),
            (68, _("Conjugate A CSM"), data.get("conjugate_csm_total", 0))
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
