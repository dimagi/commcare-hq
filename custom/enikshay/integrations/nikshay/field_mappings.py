gender_mapping = {
    'male': 'M',
    'female': 'F',
    'transgender': 'T',
}

disease_classification = {
    'pulmonary': 'P',
    'extra_pulmonary': 'EP',
}

patient_type_choice = {
    'new': '1',
    'recurrent': '2',
    'other_previously_treated': '3',
    'treatment_after_failure': '4',
    'other_previously_treated': '5',
    'treatment_after_lfu': '6',
    'transfer_in': '7',
}

treatment_support_designation = {
    'health_worker': '1',
    'tbhv': '2',
    'asha_or_other_phi_hw': '3',
    'aww': '4',
    'ngo_volunteer': '5',
    'private_medical_pracitioner': '6',
    'other_community_volunteer': '7',
}

occupation = {
    'air_force': 7,
    'business_person': 7,
    'charity_social_work': 7,
    'chartered_accountant': 7,
    'college_university_teacher': 6,
    'diplomat': 1,
    'doctor_': 5,
    'engineer': 4,
    'government_service': 1,
    'house_maker': 7,
    'journalist': 7,
    'labour': 27,
    'lawyer': 11,
    'media': 7,
    'military': 7,
    'navy': 7,
    'news_broadcaster': 7,
    'other': 7,
    'police': 7,
    'private_service': 7,
    'publisher': 7,
    'reporter': 7,
    'researcher': 6,
    'retired': 30,
    'self-employed_freelancer': 7,
    'student': 6,
    'trader': 21,
    'unemployed': 28,
    'worker': 29,
    'writer': 7,
}

episode_site = {
    'lymph_node': 1,
    'pleural_effusion': 2,
    'abdominal': 3,
    'others': 10,
}
dcpulmonory = {
    'pulmonary': 'Y',
    'extra_pulmonary': 'N',
}

dcexpulmonory = {
    'pulmonary': 'N',
    'extra_pulmonary': 'Y',
}

treatment_outcome = {
    'cured': '1',
    'treatment_complete': '2',
    'died': '3',
    'failure': '4',
    'regimen_changed': '7',
    'loss_to_follow_up': '5',
}

hiv_status = {
    'reactive': 'Pos',
    'non_reactive': 'Neg',
    'unknown': 'Unknown',
}

art_initiated = {
    'no': 0,
    'yes': 1,
}

purpose_of_testing = {
    'end_of_ip': 1,
    'end_of_cp': 4,
}

smear_result_grade = {
    '0': 99,  # Negative
    'SC-0': 98,  # Positive
    'SC-1': 1,
    'SC-2': 2,
    'SC-3': 3,
    'SC-4': 4,
    'SC-5': 5,
    'SC-6': 6,
    'SC-7': 7,
    'SC-8': 8,
    'SC-9': 9,
    '1+': 11,
    '2+': 12,
    '3+': 13,
}

drug_susceptibility_test_status = {
    'pending': 'N',
    'not_done': 'N',
    'rif_sensitive': 'S',
    'rif_resistant': 'R',
    'xdr': 'N'
}

basis_of_diagnosis = {
    'clinical_chest': 'X',
    'clinical_other': 'E',
    'microbiological_smear': 'S',
    'microbiological_cbnaat': 'M',
    'microbiological_culture': 'C',
    'microbiological_pcr': 'M',
    'microbiological_other': 'M',
}
