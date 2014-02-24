from django.utils.translation import ugettext as _
from sqlagg import SumColumn
from corehq.apps.locations.models import Location
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn


class AncHmisCaseSqlData(SqlData):

    table_name = "fluff_AncHmisCaseFluff"

    def __init__(self, domain, datespan, location_id):
        self.domain = domain
        self.datespan = datespan
        self.parent_location = Location.get(location_id)
        self.location_ids = [location_id] + [location.get_id for location in self.parent_location.descendants]
        self.location_ids = "','".join(self.location_ids)

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc.date(),
            enddate=self.datespan.enddate_utc.date(),
            location_ids=self.location_ids
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



