from casexml.apps.case.models import CommCareCase
import fluff
from corehq.apps.users.models import CommCareUser
from custom.m4change import user_calcs
from custom.m4change.constants import M4CHANGE_DOMAINS


def _get_case_location_id(case):
    if case.user_id is not None:
        user = CommCareUser.get_by_user_id(userID=case.user_id, domain=case.domain)
        if user is not None and 'location_id' in user.get_domain_membership(case.domain):
            return user.get_domain_membership(case.domain).location_id
        else:
            return 'None'


class AncHmisCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    domains = M4CHANGE_DOMAINS
    group_by = ('domain',)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    attendance = user_calcs.AncAntenatalAttendanceCalculator()
    attendance_before_20_weeks = user_calcs.AncAntenatalVisitBefore20WeeksCalculator()
    attendance_after_20_weeks = user_calcs.AncAntenatalVisitAfter20WeeksCalculator()
    attendance_gte_4_visits = user_calcs.AncAttendanceGreaterEqual4VisitsCalculator()
    anc_syphilis_test_done = user_calcs.AncSyphilisTestDoneCalculator()
    anc_syphilis_test_positive = user_calcs.AncSyphilisPositiveCalculator()
    anc_syphilis_case_treated = user_calcs.AncSyphilisCaseTreatedCalculator()
    pregnant_mothers_receiving_ipt1 = user_calcs.PregnantMothersReceivingIpt1Calculator()
    pregnant_mothers_receiving_ipt2 = user_calcs.PregnantMothersReceivingIpt2Calculator()
    pregnant_mothers_receiving_llin = user_calcs.PregnantMothersReceivingLlinCalculator()
    pregnant_mothers_receiving_ifa = user_calcs.PregnantMothersReceivingIfaCalculator()
    postnatal_attendance = user_calcs.PostnatalAttendanceCalculator()
    postnatal_clinic_visit_lte_1_day = user_calcs.PostnatalClinicVisitWithin1DayOfDeliveryCalculator()
    postnatal_clinic_visit_lte_3_days = user_calcs.PostnatalClinicVisitWithin3DaysOfDeliveryCalculator()
    postnatal_clinic_visit_gte_7_days = user_calcs.PostnatalClinicVisitGreaterEqual7DaysOfDeliveryCalculator()


AncHmisCaseFluffPillow = AncHmisCaseFluff.pillow()


class ImmunizationHmisCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase
    domains = M4CHANGE_DOMAINS
    group_by = ('domain',)
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    opv_0 = user_calcs.PncImmunizationCalculator("opv_0")
    hep_b_0 = user_calcs.PncImmunizationCalculator("hep_b_0")
    bcg = user_calcs.PncImmunizationCalculator("bcg")
    opv_1 = user_calcs.PncImmunizationCalculator("opv_1")
    hep_b_1 = user_calcs.PncImmunizationCalculator("hep_b_1")
    penta_1 = user_calcs.PncImmunizationCalculator("penta_1")
    dpt_1 = user_calcs.PncImmunizationCalculator("dpt_1")
    pcv_1 = user_calcs.PncImmunizationCalculator("pcv_1")
    opv_2 = user_calcs.PncImmunizationCalculator("opv_2")
    hep_b_2 = user_calcs.PncImmunizationCalculator("hep_b_2")
    penta_2 = user_calcs.PncImmunizationCalculator("penta_2")
    dpt_2 = user_calcs.PncImmunizationCalculator("dpt_2")
    pcv_2 = user_calcs.PncImmunizationCalculator("pcv_2")
    opv_3 = user_calcs.PncImmunizationCalculator("opv_3")
    penta_3 = user_calcs.PncImmunizationCalculator("penta_3")
    dpt_3 = user_calcs.PncImmunizationCalculator("dpt_3")
    pcv_3 = user_calcs.PncImmunizationCalculator("pcv_3")
    measles_1 = user_calcs.PncImmunizationCalculator("measles_1")
    fully_immunized = user_calcs.PncFullImmunizationCalculator()
    yellow_fever = user_calcs.PncImmunizationCalculator("yellow_fever")
    measles_2 = user_calcs.PncImmunizationCalculator("measles_2")
    conjugate_csm = user_calcs.PncImmunizationCalculator("conjugate_csm")

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
        'domain',
        fluff.AttributeGetter('mother_id', getter_function=_get_case_mother_id),
    )
    save_direct_to_sql = True

    location_id = fluff.FlatField(_get_case_location_id)
    women_registered_anc = user_calcs.AncRegistrationCalculator()
    women_having_4_anc_visits = user_calcs.Anc4VisitsCalculator()
    women_delivering_at_facility_cct = user_calcs.FacilityDeliveryCctCalculator()
    women_delivering_within_6_weeks_attending_pnc = user_calcs.PncAttendanceWithin6WeeksCalculator()

ProjectIndicatorsCaseFluffPillow = ProjectIndicatorsCaseFluff.pillow()
