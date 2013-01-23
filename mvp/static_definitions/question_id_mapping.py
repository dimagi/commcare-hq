"""
    Eventually the creation of new indicators should be part of a UI. This is a temporary solution.
"""

def _make_qid(question_id, version):
    return {
        'question_id': question_id,
        'version': version,
    }

CHILD_VISIT_QUESTION_IDS = {
    'immediate_danger_sign': {
        'mvp-sauri': _make_qid('patient_available.immediate_danger_sign', 1),
        'mvp-potou': _make_qid('patient_available.immediate_danger_sign', 1),
    },
    'emergency_danger_sign': {
        'mvp-sauri': _make_qid('patient_available.emergency_danger_sign', 1),
        'mvp-potou': _make_qid('patient_available.emergency_danger_sign', 1),
    },
    'visit_hospital': {
        'mvp-sauri': _make_qid('visit_hospital', 1),
        'mvp-potou': _make_qid('visit_hospital', 1),
    },
    'rdt_result': {
        'mvp-sauri': _make_qid('patient_available.referral_follow_on.rdt_result', 1),
        'mvp-potou': _make_qid('patient_available.referral_follow_on.rdt_result', 1),
    },
    'fever_medication': {
        'mvp-sauri': _make_qid('patient_available.fever_medication', 1),
        'mvp-potou': _make_qid('patient_available.medication_type', 1),
    },
    'diarrhea_medication': {
        'mvp-sauri': _make_qid('patient_available.diarrhea_medication', 1),
        'mvp-potou': _make_qid('patient_available.medication_type', 1),
    },
    'referral_type': {
        'mvp-sauri': _make_qid('patient_available.referral_type', 1),
        'mvp-potou': _make_qid('patient_available.referral_type', 1),
    },
    'muac': {
        'mvp-sauri': _make_qid('patient_available.muac', 1),
        'mvp-potou': _make_qid('patient_available.muac', 1),
    },
    'exclusive_breastfeeding': {
        'mvp-sauri': _make_qid('group_counseling.exclusive_breastfeeding', 1),
        'mvp-potou': _make_qid('group_counseling.exclusive_breastfeeding', 1),
    },
    'vaccination_status': {
        'mvp-sauri': _make_qid('group_counseling.vaccinations_up_to_date', 1),
        'mvp-potou': _make_qid('patient_available.vaccination_birth', 1),
    },
    'vaccination_status_6weeks': {
        'mvp-potou': _make_qid('patient_available.vaccination_6week', 1),
    },
    'vaccination_status_10weeks': {
        'mvp-potou': _make_qid('patient_available.vaccination_10week', 1),
    },
    'vaccination_status_14weeks': {
        'mvp-potou': _make_qid('patient_available.vaccination_14week', 1),
    },
    'vaccination_status_36weeks': {
        'mvp-potou': _make_qid('patient_available.vaccination_36week', 1),
    },
}

CHILD_REGISTRATION_QUESTION_IDS = {
    'delivered_in_facility': {
        'mvp-sauri': _make_qid('delivered_in_facility', 1),
        'mvp-potou': _make_qid('delivered_in_facility', 1),
    },
    'weight_at_birth': {
        'mvp-sauri': _make_qid('weight_at_birth', 1),
        'mvp-potou': _make_qid('weight_at_birth', 1),
    },
}

PREGNANCY_VISIT_QUESTION_IDS = {
    'immediate_danger_sign': {
        'mvp-sauri': _make_qid('patient_available.immediate_danger_sign', 1),
        'mvp-potou': _make_qid('immediate_danger_sign', 1),
    },
    'emergency_danger_sign': {
        'mvp-sauri': _make_qid('emergency_danger_sign', 1),
        'mvp-potou': _make_qid('emergency_danger_sign', 1),
    },
    'prev_num_anc': {
        'mvp-sauri': _make_qid('prev_num_anc', 2),
        'mvp-potou': _make_qid('prev_cur_num_anc', 2),
    },
    'num_anc': {
        'mvp-sauri': _make_qid('group_counseling.num_anc', 1),
        'mvp-potou': _make_qid('group_referral_dangersign.num_anc', 2),
    },
    'cur_num_anc': {
        'mvp-sauri': _make_qid('cur_num_anc', 1),
        'mvp-potou': _make_qid('cur_num_anc', 1),
    },
    'last_anc_date': {
        'mvp-sauri': _make_qid('group_counseling.last_anc_date', 1),
    },
    'last_anc_weeks': {
        'mvp-potou': _make_qid('group_referral_dangersign.last_anc_weeks', 2),
    },
    'referral_type': {
        'mvp-sauri': _make_qid('group_referral_dangersign.referral_type', 3),
        'mvp-potou': _make_qid('referral_type', 2),
    },
}

HOUSEHOLD_VISIT_QUESTION_IDS = {
    'num_using_fp': {
        'mvp-sauri': _make_qid('num_using_fp', 1),
        'mvp-potou': _make_qid('num_using_fp', 1),
    },
    'num_ec': {
        'mvp-sauri': _make_qid('num_ec', 1),
        'mvp-potou': _make_qid('num_ec', 1),
    },
    'num_other_positive': {
        'mvp-sauri': _make_qid('num_other_positive', 1),
        'mvp-potou': _make_qid('num_other_positive', 1),
    },
    'num_antimalarials_other': {
        'mvp-sauri': _make_qid('num_antimalarials_other', 1),
        'mvp-potou': _make_qid('num_antimalarials_other', 1),
    }
}

CHILD_CLOSE_FORM_QUESTION_IDS = {
    'close_reason': {
        'mvp-sauri': _make_qid('reason', 2),
        'mvp-potou': _make_qid('reason', 2),
    },
    'date_of_death': {
        'mvp-sauri': _make_qid('date_of_death', 2),
        'mvp-potou': _make_qid('date_of_death', 2),
    },
}

PREGNANCY_CLOSE_FORM_QUESTION_IDS = dict(
    close_reason={
        'mvp-sauri': _make_qid('close_reason', 2),
        'mvp-potou': _make_qid('close_reason', 2),
    },
    termination_reason={
        'mvp-sauri': _make_qid('termination_reason', 1),
        'mvp-potou': _make_qid('termination_reason', 1),
    },
    pregnancy_termination={
        'mvp-sauri': _make_qid('date_of_termination', 1),
        'mvp-potou': _make_qid('date_of_termination', 1),
        }
)
