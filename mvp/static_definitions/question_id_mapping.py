"""
    Eventually the creation of new indicators should be part of a UI. This is a temporary solution.
"""

CHILD_VISIT_QUESTION_IDS = {
    'immediate_danger_sign': {
        'mvp-sauri': ('patient_available.immediate_danger_sign', 1), # ('<question_id>', <version #>)
        'mvp-potou': ('patient_available.immediate_danger_sign', 1),
    },
    'emergency_danger_sign': {
        'mvp-sauri': ('patient_available.emergency_danger_sign', 1),
        'mvp-potou': ('patient_available.emergency_danger_sign', 1),
    },
    'visit_hospital': {
        'mvp-sauri': ('visit_hospital', 1),
        'mvp-potou': ('visit_hospital', 1),
    },
    'rdt_result': {
        'mvp-sauri': ('patient_available.referral_follow_on.rdt_result', 1),
        'mvp-potou': ('patient_available.referral_follow_on.rdt_result', 1),
    },
    'fever_medication': {
        'mvp-sauri': ('patient_available.fever_medication', 1),
        'mvp-potou': ('patient_available.medication_type', 1),
    },
    'diarrhea_medication': {
        'mvp-sauri': ('patient_available.diarrhea_medication', 1),
        'mvp-potou': ('patient_available.medication_type', 1),
    },
    'referral_type': {
        'mvp-sauri': ('patient_available.referral_type', 1),
        'mvp-potou': ('patient_available.referral_type', 1),
    },
    'muac': {
        'mvp-sauri': ('patient_available.muac', 1),
        'mvp-potou': ('patient_available.muac', 1),
    },
    'exclusive_breastfeeding': {
        'mvp-sauri': ('group_counseling.exclusive_breastfeeding', 1),
        'mvp-potou': ('group_counseling.exclusive_breastfeeding', 1),
    },
}

PREGNANCY_VISIT_QUESTION_IDS = {
    'immediate_danger_sign': {
        'mvp-sauri': ('patient_available.immediate_danger_sign', 1),
        'mvp-potou': ('immediate_danger_sign', 1),
    },
    'emergency_danger_sign': {
        'mvp-sauri': ('emergency_danger_sign', 1),
        'mvp-potou': ('emergency_danger_sign', 1),
    },
    'prev_num_anc': {
        'mvp-sauri': ('group_counseling.prev_num_anc', 1),
        'mvp-potou': ('prev_num_anc', 1),
    },
    'num_anc': {
        'mvp-sauri': ('group_counseling.num_anc', 1),
        'mvp-potou': ('group_counseling.num_anc', 1),
    },
    'last_anc_date': {
        'mvp-sauri': ('group_counseling.last_anc_date', 1),
    },
    'last_anc_weeks': {
        'mvp-potou': ('group_counseling.last_anc_weeks', 1),
    },
    'referral_type': {
        'mvp-sauri': ('group_referral_dangersign.referral_type', 1),
        'mvp-potou': ('group_referral_dangersign.referral_type', 1),
    },
}

HOUSEHOLD_VISIT_QUESTION_IDS = {
    'num_using_fp': {
        'mvp-sauri': ('num_using_fp', 1),
        'mvp-potou': ('num_using_fp', 1),
    },
    'num_ec': {
        'mvp-sauri': ('num_ec', 1),
        'mvp-potou': ('num_ec', 1),
    },
}

CHILD_CLOSE_FORM_QUESTION_IDS = {
    'close_reason': {
        'mvp-sauri': ('reason', 2),
        'mvp-potou': ('reason', 2),
    },
    'date_of_death': {
        'mvp-sauri': ('date_of_death', 2),
        'mvp-potou': ('date_of_death', 2),
    },
}

PREGNANCY_CLOSE_FORM_QUESTION_IDS = dict(
    close_reason={
        'mvp-sauri': ('close_reason', 2),
        'mvp-potou': ('close_reason', 2),
    },
    termination_reason={
        'mvp-sauri': ('termination_reason', 1),
        'mvp-potou': ('termination_reason', 1),
    },
    pregnancy_termination={
        'mvp-sauri': ('date_of_termination', 1),
        'mvp-potou': ('date_of_termination', 1),
        }
)
