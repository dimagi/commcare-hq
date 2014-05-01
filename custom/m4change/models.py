from datetime import date
from couchdbkit import NoResultFound, MultipleResultsFound, ResourceNotFound, QueryMixin
from couchdbkit.ext.django.schema import StringProperty, DateProperty, DictProperty, Document
from django.db import models
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
import fluff
from fluff.filters import ORFilter
import operator
from corehq import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.users.models import CommCareUser
from corehq.fluff.calculators import case as ccalc
from custom.m4change.user_calcs import anc_hmis_report_calcs, ld_hmis_report_calcs, immunization_hmis_report_calcs,\
    all_hmis_report_calcs, project_indicators_report_calcs, mcct_monthly_aggregate_report_calcs, is_valid_user_by_case, \
    form_passes_filter_date_delivery, form_passes_filter_date_modified, case_passes_filter_date_modified, \
    case_passes_filter_date_delivery
from custom.m4change.constants import M4CHANGE_DOMAINS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, MOTHER_CASE_TYPE, \
    CHILD_CASE_TYPE, BOOKED_DELIVERY_FORMS, UNBOOKED_DELIVERY_FORMS
from operator import contains, eq

NO_VALUE_STRING = "None"

def _get_location_by_user_id(user_id, domain):
    user = CommCareUser.get(user_id)
    if user is not None:
        location_id = get_commtrack_location_id(user, Domain.get_by_name(domain))
        return str(location_id) if location_id is not None else NO_VALUE_STRING
    return NO_VALUE_STRING

def _get_case_location_id(case):
    if is_valid_user_by_case(case):
        return _get_location_by_user_id(case.user_id, case.domain)
    return NO_VALUE_STRING

def _get_form_location_id(form):
    user_id = form.form.get("meta", {}).get("userID", None)
    if user_id not in [None, "", "demo_user"]:
        return _get_location_by_user_id(user_id, form.domain)
    return NO_VALUE_STRING

def _get_user_id_by_case(case):
    if hasattr(case, "user_id") and case.user_id not in [None, "", "demo_user"]:
        return str(case.user_id)
    else:
        return NO_VALUE_STRING

def _get_user_id_by_form(form):
    user_id = form.form.get("meta", {}).get("userID", None)
    return str(user_id) if user_id not in [None, "", "demo_user"] else NO_VALUE_STRING


class BaseM4ChangeCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    document_filter = ORFilter([
        ccalc.CasePropertyFilter(type=MOTHER_CASE_TYPE),
        ccalc.CasePropertyFilter(type=CHILD_CASE_TYPE)
    ])
    domains = M4CHANGE_DOMAINS
    save_direct_to_sql = True


class AncHmisCaseFluff(BaseM4ChangeCaseFluff):
    group_by = ("domain",)

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


class LdHmisCaseFluff(BaseM4ChangeCaseFluff):
    group_by = ("domain",)

    location_id = fluff.FlatField(_get_case_location_id)
    deliveries = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"pregnancy_outcome": {"value": "live_birth", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    deliveries_svd = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"delivery_type": {"value": "svd", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    deliveries_assisted = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"delivery_type": {"value": "assisted", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    deliveries_caesarean_section = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"delivery_type": {"value": "cs", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    deliveries_complications = ld_hmis_report_calcs.DeliveriesComplicationsCalculator()
    deliveries_preterm = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"term_status": {"value": "pre_term", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    deliveries_hiv_positive_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"hiv_test_result": {"value": "positive", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    live_birth_hiv_positive_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"hiv_test_result": {"value": "positive", "comparator": eq},
         "pregnancy_outcome": {"value": "live_birth", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    deliveries_hiv_positive_booked_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"hiv_test_result": {"value": "positive", "comparator": eq}},
        BOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    deliveries_hiv_positive_unbooked_women = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"hiv_test_result": {"value": "positive", "comparator": eq}},
        UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, MOTHER_CASE_TYPE
    )
    # deliveries_monitored_using_partograph = ld_hmis_report_calcs.LdKeyValueDictCalculator(
    #     {"": ""}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, _form_passes_filter_date_delivery
    # )
    # deliveries_skilled_birth_attendant = ld_hmis_report_calcs.LdKeyValueDictCalculator(
    #     {"": ""}, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, _form_passes_filter_date_delivery
    # )
    tt1 = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"tt1": {"value": "yes", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_modified, MOTHER_CASE_TYPE
    )
    tt2 = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"tt2": {"value": "yes", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_modified, MOTHER_CASE_TYPE
    )
    live_births_male_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"pregnancy_outcome": {"value": "live_birth", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
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
        {"pregnancy_outcome": {"value": "still_birth", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    fresh_still_births = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"type_still_birth": {"value": "fresh_still_birth", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    other_still_births = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"type_still_birth": {"value": "other_still_birth", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    abortion_induced = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"abortion_type": {"value": "induced_abortion", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    other_abortions = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"abortion_type": {"value": "no_other_abortion", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    total_abortions = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"pregnancy_outcome": {"value": "abortion", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    birth_asphyxia = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_birth_asphyxia", "comparator": contains}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    birth_asphyxia_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_birth_asphyxia", "comparator": contains},
         "baby_sex": {"value": "male", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    birth_asphyxia_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_birth_asphyxia", "comparator": contains},
         "baby_sex": {"value": "female", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_sepsis = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_sepsis", "comparator": contains}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_sepsis_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_sepsis", "comparator": contains},
         "baby_sex": {"value": "male", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_sepsis_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_sepsis", "comparator": contains},
         "baby_sex": {"value": "female", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_tetanus = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_tetanus", "comparator": contains}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_tetanus_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_tetanus", "comparator": contains},
         "baby_sex": {"value": "male", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_tetanus_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_tetanus", "comparator": contains},
         "baby_sex": {"value": "female", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_jaundice = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_jaundice", "comparator": contains}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_jaundice_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_jaundice", "comparator": contains},
         "baby_sex": {"value": "male", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    neonatal_jaundice_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "neonatal_jaundice", "comparator": contains},
         "baby_sex": {"value": "female", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    low_birth_weight_babies_in_kmc = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "kmc", "comparator": contains}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    low_birth_weight_babies_in_kmc_male = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "kmc", "comparator": contains},
         "baby_sex": {"value": "male", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
    )
    low_birth_weight_babies_in_kmc_female = ld_hmis_report_calcs.LdKeyValueDictCalculator(
        {"birth_complication": {"value": "kmc", "comparator": contains},
         "baby_sex": {"value": "female", "comparator": eq}},
        BOOKED_AND_UNBOOKED_DELIVERY_FORMS, form_passes_filter_date_delivery, CHILD_CASE_TYPE
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


class ImmunizationHmisCaseFluff(BaseM4ChangeCaseFluff):
    group_by = ("domain",)

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


class ProjectIndicatorsCaseFluff(BaseM4ChangeCaseFluff):
    group_by = (
        "domain",
        fluff.AttributeGetter("mother_id", getter_function=_get_case_mother_id),
    )

    location_id = fluff.FlatField(_get_case_location_id)
    user_id = fluff.FlatField(_get_user_id_by_case)
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
    user_id = fluff.FlatField(_get_user_id_by_form)
    eligible_due_to_registration = mcct_monthly_aggregate_report_calcs.EligibleDueToRegistrationCalculator()
    eligible_due_to_4th_visit = mcct_monthly_aggregate_report_calcs.EligibleDueTo4thVisitCalculator()
    eligible_due_to_delivery = mcct_monthly_aggregate_report_calcs.EligibleDueToDeliveryCalculator()
    eligible_due_to_immun_or_pnc_visit = mcct_monthly_aggregate_report_calcs.EligibleDueToImmunizationOrPncVisitCalculator()
    status = mcct_monthly_aggregate_report_calcs.StatusCalculator()

McctMonthlyAggregateFormFluffPillow = McctMonthlyAggregateFormFluff.pillow()


class AllHmisCaseFluff(BaseM4ChangeCaseFluff):
    group_by = ("domain",)

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


class FixtureReportResult(Document, QueryMixin):
    domain = StringProperty()
    location_id = StringProperty()
    start_date = DateProperty()
    end_date = DateProperty()
    report_slug = StringProperty()
    rows = DictProperty()
    name = StringProperty()

    class Meta:
        app_label = "m4change"

    @classmethod
    def by_composite_key(cls, domain, location_id, start_date, end_date, report_slug):
        try:
            return cls.view("m4change/fixture_by_composite_key",
                             key=[domain, location_id, start_date, end_date, report_slug],
                             include_docs=True).one(except_all=True)
        except (NoResultFound, ResourceNotFound, MultipleResultsFound):
            return None

    @classmethod
    def by_domain(cls, domain):
        return cls.view("m4change/fixture_by_composite_key", startkey=[domain], endkey=[domain, {}], include_docs=True).all()

    @classmethod
    def get_report_results_by_key(cls, domain, location_id, start_date, end_date):
        return cls.view("m4change/fixture_by_composite_key",
                        startkey=[domain, location_id, start_date, end_date],
                        endkey=[domain, location_id, start_date, end_date, {}],
                        include_docs=True).all()

    @classmethod
    def _validate_params(cls, params):
        for param in params:
            if param is None or len(param) == 0:
                return False
        return True

    @classmethod
    def save_result(cls, domain, location_id, start_date, end_date, report_slug, rows, name):
        if not cls._validate_params([domain, location_id, report_slug]) \
                or not isinstance(rows, dict) or len(rows) == 0 \
                or not isinstance(start_date, date) or not isinstance(end_date, date):
            return
        FixtureReportResult(domain=domain, location_id=location_id, start_date=start_date, end_date=end_date,
                            report_slug=report_slug, rows=rows, name=name).save()


from .signals import *
