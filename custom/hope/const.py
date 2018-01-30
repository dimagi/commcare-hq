
MOTHER_OTHER_PROPERTIES = [
    ('mother_name', '_HOPE_mother_mother_name'),
    ('husband_name', '_HOPE_mother_husband_name'),
    ('program_cd', '_HOPE_mother_program_cd'),
    ('bank_account_number', '_HOPE_mother_bank_account_number'),
    ('bank_id', '_HOPE_mother_bank_id'),
    ('bank_branch_id', '_HOPE_mother_bank_branch_id'),
    ('ifsc_code', '_HOPE_mother_ifsc_code'),
    ('full_mcts_id', '_HOPE_mother_full_mcts_id'),
    ('agency_cd', '_HOPE_agency_cd'),
    ('asha_id', '_HOPE_asha_id'),
    ('asha_bank_account_number', '_HOPE_asha_bank_account_number'),
    ('asha_bank_id', '_HOPE_asha_bank_id'),
    ('asha_bank_branch_id', '_HOPE_asha_bank_branch_id'),
    ('asha_ifsc_code', '_HOPE_asha_ifsc_code')
]

CHILD_OTHER_PROPERTIES = [
    ('mother_name', '_HOPE_child_parent_mother_name'),
    ('husband_name', '_HOPE_child_parent_husband_name'),
    ('bank_account_number', '_HOPE_child_parent_bank_account_number'),
    ('bank_id', '_HOPE_child_parent_bank_id'),
    ('bank_branch_id', '_HOPE_child_parent_bank_branch_id'),
    ('ifsc_code', '_HOPE_child_parent_ifsc_code'),
    ('full_mcts_id', '_HOPE_child_parent_full_mcts_id'),
    ('full_child_mcts_id', '_HOPE_child_full_child_mcts_id'),
    ('agency_cd', '_HOPE_agency_cd'),
    ('asha_id', '_HOPE_asha_id'),
    ('asha_bank_account_number', '_HOPE_asha_bank_account_number'),
    ('asha_bank_id', '_HOPE_asha_bank_id'),
    ('asha_bank_branch_id', '_HOPE_asha_bank_branch_id'),
    ('asha_ifsc_code', '_HOPE_asha_ifsc_code')
]

MOTHER_EVENTS_ATTRIBUTES = [
    ('ANC', 'anc_1_date', '_HOPE_mother_anc_1_date'),
    ('ANC', 'anc_2_date', '_HOPE_mother_anc_2_date'),
    ('ANC', 'anc_3_date', '_HOPE_mother_anc_3_date'),
    ('ANC', 'anc_4_date', '_HOPE_mother_anc_4_date'),
    ('ANC', 'all_anc_doses_given', '_HOPE_mother_all_anc_doses_given'),

    ('DLYT', 'patient_reg_num', '_HOPE_mother_patient_reg_num'),
    ('DLYT', 'registration_date', '_HOPE_mother_registration_date'),
    ('DLYT', 'existing_child_count', '_HOPE_mother_existing_child_count'),
    ('DLYT', 'age_of_beneficiary', '_HOPE_mother_age'),
    ('DLYT', 'bpl_indicator', '_HOPE_mother_bpl_indicator'),
    ('DLYT', 'delivery_date', '_HOPE_mother_delivery_date'),
    ('DLYT', 'time_of_birth', '_HOPE_mother_time_of_birth'),
    ('DLYT', 'tubal_ligation', '_HOPE_mother_tubal_ligation'),
    ('DLYT', 'area_indicator', '_HOPE_mother_area_indicator'),

    ('IFA', 'ifa1_date', '_HOPE_mother_ifa1_date'),
    ('IFA', 'ifa2_date', '_HOPE_mother_ifa2_date'),
    ('IFA', 'ifa3_date', '_HOPE_mother_ifa3_date'),
    ('IFA', 'all_ifa_doses_given',  '_HOPE_mother_all_ifa_doses_given'),

    ('TT', 'tt_1_date', '_HOPE_mother_tt_1_date'),
    ('TT', 'tt_2_date', '_HOPE_mother_tt_2_date'),
    ('TT', 'all_tt_doses_given', '_HOPE_mother_all_tt_doses_given'),
]

CHILD_EVENTS_ATTRIBUTES = [
    ('PNC', 'child_name', '_HOPE_child_child_name'),
    ('PNC', 'mother_name', '_HOPE_child_mother_name'),
    ('PNC', 'number_of_visits', '_HOPE_child_number_of_visits'),
    ('PNC', 'bcg_indicator', '_HOPE_child_bcg_indicator'),
    ('PNC', 'opv_1_indicator', '_HOPE_child_opv_1_indicator'),
    ('PNC', 'dpt_1_indicator', '_HOPE_child_dpt_1_indicator'),
    ('PNC', 'delivery_type', '_HOPE_child_delivery_type'),

    ('MSLS', 'child_name', '_HOPE_child_child_name'),
    ('MSLS', 'mother_name', '_HOPE_child_mother_name'),
    ('MSLS', 'husband_name', '_HOPE_child_mother_husband_name'),
    ('MSLS', 'dpt_1_date', '_HOPE_child_dpt_1_date'),
    ('MSLS', 'opv_1_date', '_HOPE_child_opv_1_date'),
    ('MSLS', 'hep_b_1_date', '_HOPE_child_hep_b_1_date'),
    ('MSLS', 'dpt_2_date', '_HOPE_child_dpt_2_date'),
    ('MSLS', 'opv_2_date', '_HOPE_child_opv_2_date'),
    ('MSLS', 'hep_b_2_date', '_HOPE_child_hep_b_2_date'),
    ('MSLS', 'dpt_3_date', '_HOPE_child_dpt_3_date'),
    ('MSLS', 'opv_3_date', '_HOPE_child_opv_3_date'),
    ('MSLS', 'hep_b_3_date', '_HOPE_child_hep_b_3_date'),
    ('MSLS', 'measles_date', '_HOPE_child_measles_date'),
    ('MSLS', 'dob', '_HOPE_child_dob'),
    ('MSLS', 'all_dpt1_opv1_hb1_doses_given', '_HOPE_child_all_dpt1_opv1_hb1_doses_given'),
    ('MSLS', 'all_dpt2_opv2_hb2_doses_given', '_HOPE_child_all_dpt2_opv2_hb2_doses_given'),
    ('MSLS', 'all_dpt3_opv3_hb3_doses_given', '_HOPE_child_all_dpt3_opv3_hb3_doses_given'),
    ('MSLS', 'measles_dose_given', '_HOPE_child_measles_dose_given'),
]
