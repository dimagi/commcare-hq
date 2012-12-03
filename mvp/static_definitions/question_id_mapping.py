CHILD_VISIT_QUESTION_IDS = dict(
    immediate_danger_sign={
        'mvp-sauri': 'patient_available.immediate_danger_sign',
        'mvp-potou': 'patient_available.immediate_danger_sign',
        },
    emergency_danger_sign={
        'mvp-sauri': 'patient_available.emergency_danger_sign',
        'mvp-potou': 'patient_available.emergency_danger_sign',
        },
    visit_hospital={
        'mvp-sauri': 'visit_hospital',
        'mvp-potou': 'visit_hospital',
        },
    rdt_result={
        'mvp-sauri': 'patient_available.referral_follow_on.rdt_result',
        'mvp-potou': 'patient_available.referral_follow_on.rdt_result',
        },
    fever_medication={
        'mvp-sauri': 'patient_available.fever_medication',
        'mvp-potou': 'patient_available.medication_type',
        },
    diarrhea_medication={
        'mvp-sauri': 'patient_available.diarrhea_medication',
        'mvp-potou': 'patient_available.medication_type',
        },
    referral_type={
        'mvp-sauri': 'patient_available.referral_type',
        'mvp-potou': 'patient_available.referral_type',
        },
    muac={
        'mvp-sauri': 'patient_available.muac',
        'mvp-potou': 'patient_available.muac',
        },
    exclusive_breastfeeding={
        'mvp-sauri': 'group_counseling.exclusive_breastfeeding',
        'mvp-potou': 'group_counseling.exclusive_breastfeeding',
        }
)

PREGNANCY_VISIT_QUESTION_IDS = dict(
    immediate_danger_sign={
        'mvp-sauri': 'patient_available.immediate_danger_sign',
        'mvp-potou': 'immediate_danger_sign',
        },
    emergency_danger_sign={
        'mvp-sauri': 'emergency_danger_sign',
        'mvp-potou': 'emergency_danger_sign',
        },
    prev_num_anc={
        'mvp-sauri': 'group_counseling.prev_num_anc',
        'mvp-potou': 'prev_num_anc',
        },
    num_anc={
        'mvp-sauri': 'group_counseling.num_anc',
        'mvp-potou': 'group_counseling.num_anc',
        },
    last_anc_date={
        'mvp-sauri': 'group_counseling.last_anc_date',
        },
    last_anc_weeks={
        'mvp-potou': 'group_counseling.last_anc_weeks',
        },
    referral_type={
        'mvp-sauri': 'group_referral_dangersign.referral_type',
        'mvp-potou': 'group_referral_dangersign.referral_type',
        }
)

HOUSEHOLD_VISIT_QUESTION_IDS = dict(
    num_using_fp={
        'mvp-sauri': 'num_using_fp',
        'mvp-potou': 'num_using_fp',
        },
    num_ec={
        'mvp-sauri': 'num_ec',
        'mvp-potou': 'num_ec',
        }
)

CHILD_CLOSE_FORM_QUESTION_IDS = dict(
    close_reason={
        'mvp-sauri': 'reason',
        'mvp-potou': 'termination_reason',
        },
    date_of_death={
        'mvp-sauri': 'date_of_death',
        'mvp-potou': 'date_of_death',
        }
)

PREGNANCY_CLOSE_FORM_QUESTION_IDS = dict(
    close_reason={
        'mvp-sauri': 'close_reason',
        'mvp-potou': 'close_reason'
    },
    pregnancy_termination={
        'mvp-sauri': 'date_of_termination',
        'mvp-potou': 'date_of_termination',
        }
)