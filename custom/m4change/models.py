from django.db import models
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
import fluff
import operator
from corehq import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.users.models import CommCareUser
from custom.m4change.user_calcs import anc_hmis_report_calcs, ld_hmis_report_calcs, immunization_hmis_report_calcs,\
    all_hmis_report_calcs, project_indicators_report_calcs, mcct_monthly_aggregate_report_calcs, is_valid_user_by_case, \
    form_passes_filter_date_delivery, form_passes_filter_date_modified, case_passes_filter_date_modified, \
    case_passes_filter_date_delivery
from custom.m4change.constants import M4CHANGE_DOMAINS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, BOOKED_DELIVERY_FORMS, \
    UNBOOKED_DELIVERY_FORMS

NO_LOCATION_VALUE_STRING = "None"

def _get_location_by_user_id(user_id, domain):
    user = CommCareUser.get(user_id)
    if user is not None:
        location_id = get_commtrack_location_id(user, Domain.get_by_name(domain))
        return str(location_id) if location_id is not None else NO_LOCATION_VALUE_STRING
    return NO_LOCATION_VALUE_STRING

def _get_case_location_id(case):
    if is_valid_user_by_case(case):
        return _get_location_by_user_id(case.user_id, case.domain)
    return NO_LOCATION_VALUE_STRING

def _get_form_location_id(form):
    user_id = form.form.get("meta", {}).get("userID", None)
    if user_id not in [None, "", "demo_user"]:
        return _get_location_by_user_id(user_id, form.domain)
    return NO_LOCATION_VALUE_STRING


class AncHmisCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    domains = M4CHANGE_DOMAINS
    group_by = ("domain",)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    attendance = anc_hmis_report_calcs.AncAntenatalAttendanceCalculator()
    attendance_before_20_weeks = anc_hmis_report_calcs.AncAntenatalVisitBefore20WeeksCalculator()
    attendance_after_20_weeks = anc_hmis_report_calcs.AncAntenatalVisitAfter20WeeksCalculator()
    attendance_gte_4_visits = anc_hmis_report_calcs.AncAttendanceGreaterEqual4VisitsCalculator()
    anc_syphilis_test_done = anc_hmis_report_calcs.AncSyphilisTestDoneCalculator()
    anc_syphilis_test_positive = anc_hmis_report_calcs.AncSyphilisPositiveCalculator()
    anc_syphilis_case_treated = anc_hmis_report_calcs.AncSyphilisCaseTreatedCalculator()
    pregnant_mothers_receiving_ipt1 = anc_hmis_report_calcs.PregnantMothersReceivingIpt1Calculator()
    pregnant_mothers_receiving_ipt2 = anc_hmis_report_calcs.PregnantMothersReceivingIpt2Calculator()
    pregnant_mothers_receiving_llin = anc_hmis_report_calcs.PregnantMothersReceivingLlinCalculator()
    pregnant_mothers_receiving_ifa = anc_hmis_report_calcs.PregnantMothersReceivingIfaCalculator()
    postnatal_attendance = anc_hmis_report_calcs.PostnatalAttendanceCalculator()
    postnatal_clinic_visit_lte_1_day = anc_hmis_report_calcs.PostnatalClinicVisitWithin1DayOfDeliveryCalculator()
    postnatal_clinic_visit_lte_3_days = anc_hmis_report_calcs.PostnatalClinicVisitWithin3DaysOfDeliveryCalculator()
    postnatal_clinic_visit_gte_7_days = anc_hmis_report_calcs.PostnatalClinicVisitGreaterEqual7DaysOfDeliveryCalculator()


AncHmisCaseFluffPillow = AncHmisCaseFluff.pillow()


class LdHmisCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    domains = M4CHANGE_DOMAINS
    group_by = ("domain",)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    deliveries = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"pregnancy_outcome": "live_birth"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    deliveries_svd = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"delivery_type": "svd"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    deliveries_assisted = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"delivery_type": "assisted"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    deliveries_caesarean_section = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"delivery_type": "cs"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    deliveries_complications = ld_hmis_report_calcs.DeliveriesComplicationsCalculator()
    deliveries_preterm = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"term_status": "pre_term"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    deliveries_hiv_positive_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"delivery_type": "svd"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    live_birth_hiv_positive_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"hiv_test_result": "positive", "pregnancy_outcome": "live_birth"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    deliveries_hiv_positive_booked_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"hiv_test_result": "positive"}, BOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    deliveries_hiv_positive_unbooked_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"hiv_test_result": "positive"}, UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    # deliveries_monitored_using_partograph = ld_hmis_report_calcs.LdKeyValueDictCalculator(
    #     {"": ""}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, _form_passes_filter_date_delivery
    # )
    # deliveries_skilled_birth_attendant = ld_hmis_report_calcs.LdKeyValueDictCalculator(
    #     {"": ""}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, _form_passes_filter_date_delivery
    # )
    tt1 = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"tt1": "yes"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_modified
    )
    tt2 = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"tt2": "yes"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_modified
    )
    live_births_male_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"pregnancy_outcome": "live_birth"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    male_lt_2_5kg = ld_hmis_report_calcs.ChildSexWeightCalculator(
        {"baby_sex": "male"}, 2.5, '<', BOOKED_AND_UNBOOKED_DELIVERY_FORMS
    )
    male_gte_2_5kg = ld_hmis_report_calcs.ChildSexWeightCalculator(
        {"baby_sex": "male"}, 2.5, '>=', BOOKED_AND_UNBOOKED_DELIVERY_FORMS
    )
    female_lt_2_5kg = ld_hmis_report_calcs.ChildSexWeightCalculator(
        {"baby_sex": "female"}, 2.5, '<', BOOKED_AND_UNBOOKED_DELIVERY_FORMS
    )
    female_gte_2_5kg = ld_hmis_report_calcs.ChildSexWeightCalculator(
        {"baby_sex": "female"}, 2.5, '>=', BOOKED_AND_UNBOOKED_DELIVERY_FORMS
    )
    still_births = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"pregnancy_outcome": "still_birth"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    fresh_still_births = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"type_still_birth": "fresh_still_birth"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    other_still_births = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"type_still_birth": "other_still_birth"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    abortion_induced = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"abortion_type": "induced_abortion"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    other_abortions = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"abortion_type": "nn_other_abortion"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    total_abortions = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"pregnancy_outcome": "abortion"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    birth_asphyxia = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_birth_asphyxia"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    birth_asphyxia_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_birth_asphyxia", "baby_sex": "male"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    birth_asphyxia_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_birth_asphyxia", "baby_sex": "female"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_sepsis = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_sepsis"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_sepsis_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_sepsis", "baby_sex": "male"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_sepsis_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_sepsis", "baby_sex": "female"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_tetanus = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_tetanus"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_tetanus_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_tetanus", "baby_sex": "male"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_tetanus_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_tetanus", "baby_sex": "female"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_jaundice = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_jaundice"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_jaundice_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_jaundice", "baby_sex": "male"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    neonatal_jaundice_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "neonatal_jaundice", "baby_sex": "female"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    low_birth_weight_babies_in_kmc = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "kmc"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    low_birth_weight_babies_in_kmc_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "kmc", "baby_sex": "male"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    low_birth_weight_babies_in_kmc_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": "kmc", "baby_sex": "female"}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery
    )
    # newborns_low_birth_weight_discharged = ld_hmis_report_calcs.LdKeyValueDictCalculator(
    #     {"": ""}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, _form_passes_filter_date_delivery
    # )
    # newborns_low_birth_weight_discharged_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
    #     {"": ""}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, _form_passes_filter_date_delivery
    # )
    # newborns_low_birth_weight_discharged_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
    #     {"": ""}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, _form_passes_filter_date_delivery
    # )

LdHmisCaseFluffPillow = LdHmisCaseFluff.pillow()


class ImmunizationHmisCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    domains = M4CHANGE_DOMAINS
    group_by = ("domain",)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    opv_0 = immunization_hmis_report_calcs.PncImmunizationCalculator("opv_0")
    hep_b_0 = immunization_hmis_report_calcs.PncImmunizationCalculator("hep_b_0")
    bcg = immunization_hmis_report_calcs.PncImmunizationCalculator("bcg")
    opv_1 = immunization_hmis_report_calcs.PncImmunizationCalculator("opv_1")
    hep_b_1 = immunization_hmis_report_calcs.PncImmunizationCalculator("hep_b_1")
    penta_1 = immunization_hmis_report_calcs.PncImmunizationCalculator("penta_1")
    dpt_1 = immunization_hmis_report_calcs.PncImmunizationCalculator("dpt_1")
    pcv_1 = immunization_hmis_report_calcs.PncImmunizationCalculator("pcv_1")
    opv_2 = immunization_hmis_report_calcs.PncImmunizationCalculator("opv_2")
    hep_b_2 = immunization_hmis_report_calcs.PncImmunizationCalculator("hep_b_2")
    penta_2 = immunization_hmis_report_calcs.PncImmunizationCalculator("penta_2")
    dpt_2 = immunization_hmis_report_calcs.PncImmunizationCalculator("dpt_2")
    pcv_2 = immunization_hmis_report_calcs.PncImmunizationCalculator("pcv_2")
    opv_3 = immunization_hmis_report_calcs.PncImmunizationCalculator("opv_3")
    penta_3 = immunization_hmis_report_calcs.PncImmunizationCalculator("penta_3")
    dpt_3 = immunization_hmis_report_calcs.PncImmunizationCalculator("dpt_3")
    pcv_3 = immunization_hmis_report_calcs.PncImmunizationCalculator("pcv_3")
    measles_1 = immunization_hmis_report_calcs.PncImmunizationCalculator("measles_1")
    fully_immunized = immunization_hmis_report_calcs.PncFullImmunizationCalculator()
    yellow_fever = immunization_hmis_report_calcs.PncImmunizationCalculator("yellow_fever")
    measles_2 = immunization_hmis_report_calcs.PncImmunizationCalculator("measles_2")
    conjugate_csm = immunization_hmis_report_calcs.PncImmunizationCalculator("conjugate_csm")

ImmunizationHmisCaseFluffPillow = ImmunizationHmisCaseFluff.pillow()


def _get_case_mother_id(case):
    if hasattr(case, "parent") and case.parent is not None:
        return case.parent._id
    else:
        return case._id


class ProjectIndicatorsCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    domains = M4CHANGE_DOMAINS
    group_by = (
        "domain",
        fluff.AttributeGetter("mother_id", getter_function=_get_case_mother_id),
    )
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    women_registered_anc = project_indicators_report_calcs.AncRegistrationCalculator()
    women_having_4_anc_visits = project_indicators_report_calcs.Anc4VisitsCalculator()
    women_delivering_at_facility_cct = project_indicators_report_calcs.FacilityDeliveryCctCalculator()
    women_delivering_within_6_weeks_attending_pnc = project_indicators_report_calcs.PncAttendanceWithin6WeeksCalculator()

ProjectIndicatorsCaseFluffPillow = ProjectIndicatorsCaseFluff.pillow()


class McctStatus(models.Model):
    form_id = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20)
    domain = models.CharField(max_length=256, null=True, db_index=True)
    reason = models.CharField(max_length=32, null=True)

    def update_status(self, new_status, reason):
        if 'eligible' in new_status:
            self.delete()
        else:
            self.status = new_status
            self.reason = reason
            self.save()

    @classmethod
    def get_status_dict(cls):
        status_dict = dict()
        mcct_status_list = McctStatus.objects.filter(domain__in=[name for name in M4CHANGE_DOMAINS])
        for mcct_status in mcct_status_list:
            if mcct_status.status not in status_dict:
                status_dict[mcct_status.status] = set()
            status_dict[mcct_status.status].add((mcct_status.form_id, mcct_status.reason))
        return status_dict


class McctMonthlyAggregateFormFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    domains = M4CHANGE_DOMAINS
    group_by = ("domain",)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_form_location_id)
    eligible_due_to_registration = mcct_monthly_aggregate_report_calcs.EligibleDueToRegistrationCalculator()
    eligible_due_to_4th_visit = mcct_monthly_aggregate_report_calcs.EligibleDueTo4thVisitCalculator()
    eligible_due_to_delivery = mcct_monthly_aggregate_report_calcs.EligibleDueToDeliveryCalculator()
    eligible_due_to_immun_or_pnc_visit = mcct_monthly_aggregate_report_calcs.EligibleDueToImmunizationOrPncVisitCalculator()
    status = mcct_monthly_aggregate_report_calcs.StatusCalculator()

McctMonthlyAggregateFormFluffPillow = McctMonthlyAggregateFormFluff.pillow()


class AllHmisCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    domains = M4CHANGE_DOMAINS
    group_by = ("domain",)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    pregnant_mothers_referred_out = all_hmis_report_calcs.CaseComparisonCalculator(
        [("client_status", operator.eq, "referred_out")], case_passes_filter_date_modified
    )
    anc_anemia_test_done = all_hmis_report_calcs.CaseComparisonCalculator(
        [("tests_conducted", operator.contains, "hb")], case_passes_filter_date_modified
    )
    anc_anemia_test_positive = all_hmis_report_calcs.CaseComparisonCalculator(
        [("hb_test_result", operator.eq, "positive")], case_passes_filter_date_modified
    )
    anc_proteinuria_test_done = all_hmis_report_calcs.CaseComparisonCalculator(
        [("tests_conducted", operator.contains, "hb")], case_passes_filter_date_modified
    )
    anc_proteinuria_test_positive = all_hmis_report_calcs.CaseComparisonCalculator(
        [("protein_test_result", operator.eq, "positive")], case_passes_filter_date_modified
    )
    hiv_rapid_antibody_test_done = all_hmis_report_calcs.CaseComparisonCalculator(
        [("tests_conducted", operator.contains, "hiv")], case_passes_filter_date_modified
    )
    deaths_of_women_related_to_pregnancy = all_hmis_report_calcs.CaseComparisonCalculator(
        [("pregnancy_outcome", operator.eq, "maternal_death")], case_passes_filter_date_delivery
    )
    pregnant_mothers_tested_for_hiv = all_hmis_report_calcs.CaseComparisonCalculator(
        [("hiv_test_result", operator.eq, "positive")], case_passes_filter_date_modified
    )
    pregnant_mothers_with_confirmed_malaria = all_hmis_report_calcs.CaseComparisonCalculator(
        [("malaria_test_result", operator.eq, "positive")], case_passes_filter_date_modified
    )
    partners_of_hiv_positive_women_tested_negative = all_hmis_report_calcs.CaseComparisonCalculator(
        [("partner_hiv_status", operator.eq, "negative")], case_passes_filter_date_modified
    )
    partners_of_hiv_positive_women_tested_positive = all_hmis_report_calcs.CaseComparisonCalculator(
        [("partner_hiv_status", operator.eq, "positive")], case_passes_filter_date_modified
    )
    assessed_for_clinical_stage_eligibility = all_hmis_report_calcs.CaseComparisonCalculator(
        [("eligibility_assessment", operator.eq, "clinical_stage")], case_passes_filter_date_modified
    )
    assessed_for_clinical_cd4_eligibility = all_hmis_report_calcs.CaseComparisonCalculator(
        [("eligibility_assessment", operator.eq, "cd4")], case_passes_filter_date_modified
    )
    pregnant_hiv_positive_women_received_art = all_hmis_report_calcs.CaseComparisonCalculator(
        [("commenced_drugs", operator.contains, "3tc")], case_passes_filter_date_modified
    )
    pregnant_hiv_positive_women_received_arv = all_hmis_report_calcs.CaseComparisonCalculator(
        [("commenced_drugs", operator.contains, ["3tc", "mother_sdnvp"])], case_passes_filter_date_modified
    )
    pregnant_hiv_positive_women_received_azt = all_hmis_report_calcs.CaseComparisonCalculator(
        [("commenced_drugs", operator.contains, "azt")], case_passes_filter_date_modified
    )
    pregnant_hiv_positive_women_received_mother_sdnvp = all_hmis_report_calcs.CaseComparisonCalculator(
        [("commenced_drugs", operator.contains, "mother_sdnvp")], case_passes_filter_date_modified
    )
    infants_hiv_women_cotrimoxazole_lt_2_months = \
        all_hmis_report_calcs.InfantsBornToHivInfectedWomenCotrimoxazoleLt2Months()
    infants_hiv_women_cotrimoxazole_gte_2_months = \
        all_hmis_report_calcs.InfantsBornToHivInfectedWomenCotrimoxazoleGte2Months()
    infants_hiv_women_received_hiv_test_lt_2_months = \
        all_hmis_report_calcs.InfantsBornToHivInfectedWomenReceivedHivTestLt2Months()
    infants_hiv_women_received_hiv_test_gte_2_months = \
        all_hmis_report_calcs.InfantsBornToHivInfectedWomenReceivedHivTestGte2Months()
    infants_hiv_women_received_hiv_test_lt_18_months = \
        all_hmis_report_calcs.InfantsBornToHivInfectedWomenReceivedHivTestLt18Months()
    infants_hiv_women_received_hiv_test_gte_18_months = \
        all_hmis_report_calcs.InfantsBornToHivInfectedWomenReceivedHivTestGte18Months()
    hiv_exposed_infants_breast_feeding_receiving_arv = all_hmis_report_calcs.CaseComparisonCalculator(
        [("commenced_drugs", operator.contains, "infant_nvp")], case_passes_filter_date_modified
    )

AllHmisCaseFluffPillow = AllHmisCaseFluff.pillow()
