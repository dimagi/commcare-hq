from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
import fluff
from corehq import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.users.models import CommCareUser
from custom.m4change.user_calcs import anc_hmis_report_calcs, immunization_hmis_report_calcs,\
    project_indicators_report_calcs, mcct_monthly_aggregate_report_calcs, is_valid_user_by_case
from custom.m4change.constants import M4CHANGE_DOMAINS

def _get_location_by_user_id(user_id, domain):
    user = CommCareUser.get_by_user_id(userID=user_id, domain=domain)
    if user is not None:
        return str(get_commtrack_location_id(user, Domain.get_by_name(domain)))
    return "None"

def _get_case_location_id(case):
    if is_valid_user_by_case(case):
        return _get_location_by_user_id(case.user_id, case.domain)
    return "None"

def _get_form_location_id(form):
    user_id = form.form.get("meta", {}).get("userID", None)
    if user_id not in [None, "", "demo_user"]:
        return _get_location_by_user_id(user_id, form.domain)
    return "None"


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
    parent = case.parent
    if parent is not None:
        return parent._id
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


class McctMonthlyAggregateFormFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    domains = M4CHANGE_DOMAINS
    group_by = ("domain",)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_form_location_id)
    all_eligible_clients = mcct_monthly_aggregate_report_calcs.AllEligibleClientsCalculator()
    eligible_due_to_registration = mcct_monthly_aggregate_report_calcs.EligibleDueToRegistrationCalculator()
    eligible_due_to_4th_visit = mcct_monthly_aggregate_report_calcs.EligibleDueTo4thVisit()
    eligible_due_to_delivery = mcct_monthly_aggregate_report_calcs.EligibleDueToDelivery()
    eligible_due_to_immun_or_pnc_visit = mcct_monthly_aggregate_report_calcs.EligibleDueToImmunizationOrPncVisit()

McctMonthlyAggregateFormFluffPillow = McctMonthlyAggregateFormFluff.pillow()
