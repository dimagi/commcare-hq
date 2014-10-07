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
        return ["domain","location_id"]


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
            DatabaseColumn(_("Number of free sim cards given"),
                           SumColumn("number_of_free_sims_given_total")),
            DatabaseColumn(_("Number of MTN MNO"),
                           SumColumn("mno_mtn_total")),
            DatabaseColumn(_("Number of Etisalat MNO"),
                           SumColumn("mno_etisalat_total")),
            DatabaseColumn(_("Number of GLO MNO"),
                           SumColumn("mno_glo_total")),
            DatabaseColumn(_("Number of Airtel MNO"),
                           SumColumn("mno_airtel_total")),
        ]

    @property
    def group_by(self):
        return ["domain","mother_id","location_id"]


class LdHmisCaseSqlData(SqlData):

    table_name = "fluff_LdHmisCaseFluff"

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
            DatabaseColumn(_("Deliveries - Total"), SumColumn("deliveries_total")),
            DatabaseColumn(_("Deliveries - SVD"), SumColumn("deliveries_svd_total")),
            DatabaseColumn(_("Deliveries - Assisted"), SumColumn("deliveries_assisted_total")),
            DatabaseColumn(_("Deliveries caesarean section"), SumColumn("deliveries_caesarean_section_total")),
            DatabaseColumn(_("Deliveries - Complications"), SumColumn("deliveries_complications_total")),
            DatabaseColumn(_("Deliveries - Preterm"), SumColumn("deliveries_preterm_total")),
            DatabaseColumn(_("Deliveries - HIV positive women"), SumColumn("deliveries_hiv_positive_women_total")),
            DatabaseColumn(_("LiveBirth - HIV positive women"), SumColumn("live_birth_hiv_positive_women_total")),
            DatabaseColumn(_("Deliveries - HIV positive booked women"), SumColumn("deliveries_hiv_positive_booked_women_total")),
            DatabaseColumn(_("Deliveries - HIV positive unbooked women"), SumColumn("deliveries_hiv_positive_unbooked_women_total")),
            # DatabaseColumn(_("Deliveries - Monitored using Partograph"), SumColumn("deliveries_monitored_using_partograph_total")),
            # DatabaseColumn(_("Deliveries taken by skilled birth attendant"), SumColumn("deliveries_skilled_birth_attendant_total")),
            DatabaseColumn(_("TT1"), SumColumn("tt1_total")),
            DatabaseColumn(_("TT2"), SumColumn("tt2_total")),
            DatabaseColumn(_("Live Births(Male, Female, < 2.5kg, >= 2.5k g)"), SumColumn("live_births_male_female_total")),
            DatabaseColumn(_("Male, < 2.5kg"), SumColumn("male_lt_2_5kg_total")),
            DatabaseColumn(_("Male, >= 2.5kg"), SumColumn("male_gte_2_5kg_total")),
            DatabaseColumn(_("Female, < 2.5kg"), SumColumn("female_lt_2_5kg_total")),
            DatabaseColumn(_("Female, >= 2.5kg"), SumColumn("female_gte_2_5kg_total")),
            DatabaseColumn(_("Still Births total"), SumColumn("still_births_total")),
            DatabaseColumn(_("Fresh Still Births"), SumColumn("fresh_still_births_total")),
            DatabaseColumn(_("Other still Births"), SumColumn("other_still_births_total")),
            DatabaseColumn(_("Abortion Induced"), SumColumn("abortion_induced_total")),
            DatabaseColumn(_("Other Abortions"), SumColumn("other_abortions_total")),
            DatabaseColumn(_("Total Abortions"), SumColumn("total_abortions_total")),
            DatabaseColumn(_("Birth Asphyxia - Total"), SumColumn("birth_asphyxia_total")),
            DatabaseColumn(_("Birth Asphyxia - Male"), SumColumn("birth_asphyxia_male_total")),
            DatabaseColumn(_("Birth Asphyxia - Female"), SumColumn("birth_asphyxia_female_total")),
            DatabaseColumn(_("Neonatal Sepsis - Total"), SumColumn("neonatal_sepsis_total")),
            DatabaseColumn(_("Neonatal Sepsis - Male"), SumColumn("neonatal_sepsis_male_total")),
            DatabaseColumn(_("Neonatal Sepsis - Female"), SumColumn("neonatal_sepsis_female_total")),
            DatabaseColumn(_("Neonatal Tetanus - Total"), SumColumn("neonatal_tetanus_total")),
            DatabaseColumn(_("Neonatal Tetanus - Male"), SumColumn("neonatal_tetanus_male_total")),
            DatabaseColumn(_("Neonatal Tetanus - Female"), SumColumn("neonatal_tetanus_female_total")),
            DatabaseColumn(_("Neonatal Jaundice - Total"), SumColumn("neonatal_jaundice_total")),
            DatabaseColumn(_("Neonatal Jaundice - Male"), SumColumn("neonatal_jaundice_male_total")),
            DatabaseColumn(_("Neonatal Jaundice - Female"), SumColumn("neonatal_jaundice_female_total")),
            DatabaseColumn(_("Low birth weight babies placed in KMC - Total"), SumColumn("low_birth_weight_babies_in_kmc_total")),
            DatabaseColumn(_("Low birth weight babies placed in KMC - Male"), SumColumn("low_birth_weight_babies_in_kmc_male_total")),
            DatabaseColumn(_("Low birth weight babies placed in KMC - Female"), SumColumn("low_birth_weight_babies_in_kmc_female_total")),
            # DatabaseColumn(_("Newborns with low birth weight discharged - Total"), SumColumn("newborns_low_birth_weight_discharged_total")),
            # DatabaseColumn(_("Newborns with low birth weight discharged - Male"), SumColumn("newborns_low_birth_weight_discharged_male_total")),
            # DatabaseColumn(_("Newborns with low birth weight discharged - Female"), SumColumn("newborns_low_birth_weight_discharged_female_total")),
        ]

    @property
    def group_by(self):
        return ["domain", "location_id"]


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
        return ["domain","location_id"]


class McctMonthlyAggregateFormSqlData(SqlData):

    table_name = "fluff_McctMonthlyAggregateFormFluff"

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
            DatabaseColumn(_("Eligible beneficiaries due to registration"), SumColumn("status_eligible_due_to_registration")),
            DatabaseColumn(_("Eligible beneficiaries due to 4th visit"), SumColumn("status_eligible_due_to_4th_visit")),
            DatabaseColumn(_("Eligible beneficiaries due to delivery"), SumColumn("status_eligible_due_to_delivery")),
            DatabaseColumn(_("Eligible beneficiaries due to immunization or PNC visit"),
                           SumColumn("status_eligible_due_to_immun_or_pnc_visit")),
            DatabaseColumn(_("Reviewed beneficiaries due to registration"), SumColumn("status_reviewed_due_to_registration")),
            DatabaseColumn(_("Reviewed beneficiaries due to 4th visit"), SumColumn("status_reviewed_due_to_4th_visit")),
            DatabaseColumn(_("Reviewed beneficiaries due to delivery"), SumColumn("status_reviewed_due_to_delivery")),
            DatabaseColumn(_("Reviewed beneficiaries due to immunization or PNC visit"),
                           SumColumn("status_reviewed_due_to_immun_or_pnc_visit")),
            DatabaseColumn(_("Approved beneficiaries due to registration"), SumColumn("status_approved_due_to_registration")),
            DatabaseColumn(_("Approved beneficiaries due to 4th visit"), SumColumn("status_approved_due_to_4th_visit")),
            DatabaseColumn(_("Approved beneficiaries due to delivery"), SumColumn("status_approved_due_to_delivery")),
            DatabaseColumn(_("Approved beneficiaries due to immunization or PNC visit"),
                           SumColumn("status_approved_due_to_immun_or_pnc_visit")),
            DatabaseColumn(_("Paid beneficiaries due to registration"), SumColumn("status_paid_due_to_registration")),
            DatabaseColumn(_("Paid beneficiaries due to 4th visit"), SumColumn("status_paid_due_to_4th_visit")),
            DatabaseColumn(_("Paid beneficiaries due to delivery"), SumColumn("status_paid_due_to_delivery")),
            DatabaseColumn(_("Paid beneficiaries due to immunization or PNC visit"),
                           SumColumn("status_paid_due_to_immun_or_pnc_visit")),
            DatabaseColumn(_("Rejected beneficiaries due to incorrect phone number"), SumColumn("status_rejected_due_to_incorrect_phone_number")),
            DatabaseColumn(_("Rejected beneficiaries due to double entry"), SumColumn("status_rejected_due_to_double_entry")),
            DatabaseColumn(_("Rejected beneficiaries due to other errors"), SumColumn("status_rejected_due_to_other_errors"))
        ]

    @property
    def group_by(self):
        return ["domain","location_id"]


class AllHmisCaseSqlData(SqlData):

    table_name = "fluff_AllHmisCaseFluff"

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
            DatabaseColumn(_("Newborns with low birth weight discharged - Total"), SumColumn("newborns_low_birth_weight_discharged_total")),
            DatabaseColumn(_("Newborns with low birth weight discharged - Male"), SumColumn("newborns_low_birth_weight_discharged_male_total")),
            DatabaseColumn(_("Newborns with low birth weight discharged - Female"), SumColumn("newborns_low_birth_weight_discharged_female_total")),
            DatabaseColumn(_("Pregnant Mothers Referred out"), SumColumn("pregnant_mothers_referred_out_total")),
            DatabaseColumn(_("ANC Anemia test done"), SumColumn("anc_anemia_test_done_total")),
            DatabaseColumn(_("ANC Anemia test positive"), SumColumn("anc_anemia_test_positive_total")),
            DatabaseColumn(_("ANC Proteinuria Test done"), SumColumn("anc_proteinuria_test_done_total")),
            DatabaseColumn(_("ANC Proteinuria test positive"), SumColumn("anc_proteinuria_test_positive_total")),
            DatabaseColumn(_("HIV rapid antibody test done"), SumColumn("hiv_rapid_antibody_test_done_total")),
            DatabaseColumn(_("Deaths of women related to pregnancy"),
                           SumColumn("deaths_of_women_related_to_pregnancy_total")),
            DatabaseColumn(_("Pregnant mothers tested positive for HIV"),
                           SumColumn("pregnant_mothers_tested_for_hiv_total")),
            DatabaseColumn(_("Pregnant Mothers with confirmed Malaria"),
                           SumColumn("pregnant_mothers_with_confirmed_malaria_total")),
            DatabaseColumn(_("ANC Women with previously known HIV status(at ANC)"),
                           SumColumn("anc_women_previously_known_hiv_status_total")),
            DatabaseColumn(_("Pregnant women who received HIV counseling testing and received result at ANC"),
                           SumColumn("pregnant_women_received_hiv_counseling_and_result_anc_total")),
            DatabaseColumn(_("Pregnant women who received HIV counseling testing and received result at L&D"),
                           SumColumn("pregnant_women_received_hiv_counseling_and_result_ld_total")),
            DatabaseColumn(_("Partners of HIV positive women who tested HIV negative"),
                           SumColumn("partners_of_hiv_positive_women_tested_negative_total")),
            DatabaseColumn(_("Partners of HIV positive women who tested positive"),
                           SumColumn("partners_of_hiv_positive_women_tested_positive_total")),
            DatabaseColumn(_("Assessed for clinical stage eligibility"),
                           SumColumn("assessed_for_clinical_stage_eligibility_total")),
            DatabaseColumn(_("Assessed for cd4-count eligibility"),
                           SumColumn("assessed_for_clinical_cd4_eligibility_total")),
            DatabaseColumn(_("Pregnant HIV positive women who received ART prophylaxis for PMTCT (Triple)"),
                           SumColumn("pregnant_hiv_positive_women_received_art_total")),
            DatabaseColumn(_("Pregnant HIV positive woman who received ARV prophylaxis for PMTCT (AZT)"),
                           SumColumn("pregnant_hiv_positive_women_received_azt_total")),
            DatabaseColumn(_("Pregnant positive women who received ARV prophylaxis(SdNvP in Labor + (AZT + 3TC))"),
                           SumColumn("pregnant_hiv_positive_women_received_mother_sdnvp_total")),
            DatabaseColumn(_("Infants born to HIV infected women started on cotrimoxazole prophylaxis within 2 months"),
                           SumColumn("infants_hiv_women_cotrimoxazole_lt_2_months_total")),
            DatabaseColumn(_("Infants born to HIV infected women started on cotrimoxazole prophylaxis 2 months & above"),
                           SumColumn("infants_hiv_women_cotrimoxazole_gte_2_months_total")),
            DatabaseColumn(_("Infants born to HIV infected women who received an HIV test within two months of birth - (DNA -PCR)"),
                           SumColumn("infants_hiv_women_received_hiv_test_lt_2_months_total")),
            DatabaseColumn(_("Infants born to HIV infected women who received an HIV test after two months of birth - (DNA - PCR)"),
                           SumColumn("infants_hiv_women_received_hiv_test_gte_2_months_total")),
            DatabaseColumn(_("Infants born to HIV infected women who received an HIV test at 18 months - (HIV Rapid test)"),
                           SumColumn("infants_hiv_women_received_hiv_test_lt_18_months_total")),
            DatabaseColumn(_("Infant born to HIV infected women who tested negative to HIV Rapid test at 18 months"),
                           SumColumn("infants_hiv_women_received_hiv_test_gte_18_months_total")),
            DatabaseColumn(_("HIV exposed infants breast feeding and receiving ARV prophylaxis"),
                           SumColumn("hiv_exposed_infants_breast_feeding_receiving_arv_total"))
        ]

    @property
    def group_by(self):
        return ["domain", "location_id"]
