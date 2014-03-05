from django.utils.translation import ugettext as _
from sqlagg import SumColumn
from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn


class AncHmisCaseSqlData(SqlData):

    table_name = "fluff_AncHmisCaseFluff"

    def __init__(self, domain, datespan):
        self.domain = domain
        self.datespan = datespan

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc.date(),
            enddate=self.datespan.enddate_utc.date()
        )

    @property
    def filters(self):
        return [
            "domain = :domain",
            "date between :startdate and :enddate"
        ]

    @property
    def columns(self):
        return [
            DatabaseColumn(_("Location ID"), SimpleColumn("location_id")),
            DatabaseColumn(_("Antenatal Attendance - Total"), SumColumn("attendance_total")),
            DatabaseColumn(_("Antenatal first Visit before 20wks"), SumColumn("attendance_before_20_weeks_total")),
            DatabaseColumn(_("Antenatal first Visit after 20wks"), SumColumn("attendance_after_20_weeks_total")),
            DatabaseColumn(_("Pregnant Women that attend antenatal clinic for 4th visit during the month"),
                           SumColumn("attendance_gte_4_visits_total")),
            DatabaseColumn(_("ANC syphilis test done"), SumColumn("anc_syphilis_test_done_total")),
            DatabaseColumn(_("ANC syphilis test positive"), SumColumn("anc_syphilis_test_positive_total")),
            DatabaseColumn(_("ANC syphilis case treated"), SumColumn("anc_syphilis_case_treated_total")),
            DatabaseColumn(_("Pregnant women who receive malaria IPT1"), SumColumn("pregnant_mothers_receiving_ipt1_total")),
            DatabaseColumn(_("Pregnant women who receive malaria IPT2"), SumColumn("pregnant_mothers_receiving_ipt2_total")),
            DatabaseColumn(_("Pregnant women who receive malaria LLIN"), SumColumn("pregnant_mothers_receiving_llin_total")),
            DatabaseColumn(_("Pregnant women who receive malaria Haematinics"), SumColumn("pregnant_mothers_receiving_ifa_total")),
            DatabaseColumn(_("Postanatal Attendance - Total"), SumColumn("postnatal_attendance_total")),
            DatabaseColumn(_("Postnatal clinic visit within 1 day of delivery"), SumColumn("postnatal_clinic_visit_lte_1_day_total")),
            DatabaseColumn(_("Postnatal clinic visit within 3 days of delivery"), SumColumn("postnatal_clinic_visit_lte_3_days_total")),
            DatabaseColumn(_("Postnatal clinic visit >= 7 days of delivery"), SumColumn("postnatal_clinic_visit_gte_7_days_total"))
        ]

    @property
    def group_by(self):
        return ['domain','location_id']


class ProjectIndicatorsCaseSqlData(SqlData):

    table_name = "fluff_ProjectIndicatorsCaseFluff"

    def __init__(self, domain, datespan):
        self.domain = domain
        self.datespan = datespan

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc.date(),
            enddate=self.datespan.enddate_utc.date()
        )

    @property
    def filters(self):
        return [
            "domain = :domain",
            "date between :startdate and :enddate"
        ]

    @property
    def columns(self):
        return [
            DatabaseColumn(_("Location ID"), SimpleColumn("location_id")),
            DatabaseColumn(_("Number of pregnant women who registered for ANC (in CCT payment sites only) "),
                           SumColumn("women_registered_anc_total")),
            DatabaseColumn(_("Number of women who had 4 ANC visits (in CCT payment sites only)"),
                           SumColumn("women_having_4_anc_visits_total")),
            DatabaseColumn(_("Number of women who delivered at the facility (in CCT payment sites only)"),
                           SumColumn("women_delivering_at_facility_cct_total")),
            DatabaseColumn(_("Number of women who attended PNC within 6 weeks of delivery"),
                           SumColumn("women_delivering_within_6_weeks_attending_pnc_total")),
        ]

    @property
    def group_by(self):
        return ['domain','mother_id','location_id']


class ImmunizationHmisCaseSqlData(SqlData):

    table_name = "fluff_ImmunizationHmisCaseFluff"

    def __init__(self, domain, datespan):
        self.domain = domain
        self.datespan = datespan

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc.date(),
            enddate=self.datespan.enddate_utc.date()
        )

    @property
    def filters(self):
        return [
            "domain = :domain",
            "date between :startdate and :enddate"
        ]

    @property
    def columns(self):
        return [
            DatabaseColumn(_("Location ID"), SimpleColumn("location_id")),
            DatabaseColumn(_("OPV0 - birth "), SumColumn("opv_0_total")),
            DatabaseColumn(_("Hep.B0 - birth"), SumColumn("hep_b_0_total")),
            DatabaseColumn(_("BCG"),SumColumn("bcg_total")),
            DatabaseColumn(_("OPV1"), SumColumn("opv_1_total")),
            DatabaseColumn(_("HEP.B1"), SumColumn("hep_b_1_total")),
            DatabaseColumn(_("Penta.1"), SumColumn("penta_1_total")),
            DatabaseColumn(_("DPT1 (not when using Penta)"), SumColumn("dpt_1_total")),
            DatabaseColumn(_("PCV1"), SumColumn("pcv_1_total")),
            DatabaseColumn(_("OPV2"), SumColumn("opv_2_total")),
            DatabaseColumn(_("Hep.B2"), SumColumn("hep_b_2_total")),
            DatabaseColumn(_("Penta.2"), SumColumn("penta_2_total")),
            DatabaseColumn(_("DPT2 (not when using Penta)"), SumColumn("dpt_2_total")),
            DatabaseColumn(_("PCV2"), SumColumn("pcv_2_total")),
            DatabaseColumn(_("OPV3"), SumColumn("opv_3_total")),
            DatabaseColumn(_("Penta.3"), SumColumn("penta_3_total")),
            DatabaseColumn(_("DPT3 (not when using Penta)"), SumColumn("dpt_3_total")),
            DatabaseColumn(_("PCV3"), SumColumn("pcv_3_total")),
            DatabaseColumn(_("Measles 1"), SumColumn("measles_1_total")),
            DatabaseColumn(_("Fully Immunized (<1year)"), SumColumn("fully_immunized_total")),
            DatabaseColumn(_("Yellow Fever"), SumColumn("yellow_fever_total")),
            DatabaseColumn(_("Measles 2"), SumColumn("measles_2_total")),
            DatabaseColumn(_("Conjugate A CSM"), SumColumn("conjugate_csm_total"))
        ]

    @property
    def group_by(self):
        return ['domain','location_id']
