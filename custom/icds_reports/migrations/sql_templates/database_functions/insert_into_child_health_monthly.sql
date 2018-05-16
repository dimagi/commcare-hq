
-- Copy into child_health_monthly
CREATE OR REPLACE FUNCTION insert_into_child_health_monthly(date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename text;
  _ucr_child_monthly_table text;
  _agg_complementary_feeding_table text;
  _ucr_child_tasks_table text;
  _agg_thr_form_table text;
  _agg_gm_form_table text;
  _agg_pnc_form_table text;
  _start_date date;
  _end_date date;
  _ucr_child_health_cases_table text;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _end_date = (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 SECOND')::DATE;
  _tablename := 'child_health_monthly' || '_' || _start_date;
  _agg_gm_form_table := 'icds_dashboard_growth_monitoring_forms';
  _agg_pnc_form_table := 'icds_dashboard_child_health_postnatal_forms';
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('child_health_monthly') INTO _ucr_child_monthly_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('complementary_feeding') INTO _agg_complementary_feeding_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('child_tasks') INTO _ucr_child_tasks_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('thr_form') INTO _agg_thr_form_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('child_list') INTO _ucr_child_health_cases_table;

  EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
  ' ( ' ||
    'awc_id, ' ||
    'case_id, ' ||
    'month, ' ||
    'age_in_months, ' ||
    'open_in_month, ' ||
    'alive_in_month, ' ||
    'wer_eligible, ' ||
    'nutrition_status_last_recorded, ' ||
    'current_month_nutrition_status, ' ||
    'nutrition_status_weighed, ' ||
    'num_rations_distributed, ' ||
    'pse_eligible, ' ||
    'pse_days_attended, ' ||
    'born_in_month, ' ||
    'low_birth_weight_born_in_month, ' ||
    'bf_at_birth_born_in_month, ' ||
    'ebf_eligible, ' ||
    'ebf_in_month, ' ||
    'ebf_not_breastfeeding_reason, ' ||
    'ebf_drinking_liquid, ' ||
    'ebf_eating, ' ||
    'ebf_no_bf_no_milk, ' ||
    'ebf_no_bf_pregnant_again, ' ||
    'ebf_no_bf_child_too_old, ' ||
    'ebf_no_bf_mother_sick, ' ||
    'cf_eligible, ' ||
    'fully_immunized_eligible, ' ||
    'fully_immunized_on_time, ' ||
    'fully_immunized_late, ' ||
    'counsel_ebf, ' ||
    'counsel_adequate_bf, ' ||
    'counsel_increase_food_bf, ' ||
    'counsel_manage_breast_problems, ' ||
    'counsel_skin_to_skin, ' ||
    'counsel_immediate_breastfeeding, ' ||
    'recorded_weight, ' ||
    'recorded_height, ' ||
    'has_aadhar_id, ' ||
    'thr_eligible, ' ||
    'pnc_eligible, ' ||
    'cf_initiation_eligible, ' ||
    'height_measured_in_month, ' ||
    'current_month_stunting, ' ||
    'stunting_last_recorded, ' ||
    'wasting_last_recorded, ' ||
    'current_month_wasting, ' ||
    'valid_in_month, ' ||
    'valid_all_registered_in_month, ' ||
    'ebf_no_info_recorded, ' ||
    'dob, ' ||
    'sex, ' ||
    'age_tranche, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    'cf_in_month, ' ||
    'cf_diet_diversity, ' ||
    'cf_diet_quantity, ' ||
    'cf_handwashing, ' ||
    'cf_demo, ' ||
    'counsel_pediatric_ifa, ' ||
    'counsel_comp_feeding_vid, ' ||
    'cf_initiation_in_month ' ||
  ') (SELECT ' ||
    'awc_id, ' ||
    'case_id, ' ||
    'month, ' ||
    'age_in_months, ' ||
    'open_in_month, ' ||
    'alive_in_month, ' ||
    'wer_eligible, ' ||
    'nutrition_status_last_recorded, ' ||
    'current_month_nutrition_status, ' ||
    'nutrition_status_weighed, ' ||
    'num_rations_distributed, ' ||
    'pse_eligible, ' ||
    'pse_days_attended, ' ||
    'born_in_month, ' ||
    'low_birth_weight_born_in_month, ' ||
    'bf_at_birth_born_in_month, ' ||
    'ebf_eligible, ' ||
    '0, ' ||
    'NULL, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    'cf_eligible, ' ||
    'fully_immunized_eligible, ' ||
    'fully_immunized_on_time, ' ||
    'fully_immunized_late, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    'counsel_immediate_breastfeeding, ' ||
    'weight_recorded_in_month, ' ||
    'height_recorded_in_month, ' ||
    'has_aadhar_id, ' ||
    'thr_eligible, ' ||
    'pnc_eligible, ' ||
    'cf_initiation_eligible, ' ||
    'height_measured_in_month, ' ||
    'current_month_stunting, ' ||
    'stunting_last_recorded, ' ||
    'wasting_last_recorded, ' ||
    'current_month_wasting, ' ||
    'valid_in_month, ' ||
    'valid_all_registered_in_month, ' ||
    'ebf_eligible, ' ||
    'dob, ' ||
    'sex, ' ||
    'age_tranche, ' ||
    'caste, ' ||
    'disabled, ' ||
    'minority, ' ||
    'resident, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0 ' ||
    'FROM ' || quote_ident(_ucr_child_monthly_table) || ' WHERE month = ' || quote_literal(_start_date) || ')';

    EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx2') || ' ON ' || quote_ident(_tablename) || '(case_id)';

    EXECUTE 'CREATE INDEX ON ' || quote_ident(_tablename) || ' (cf_eligible) WHERE cf_eligible = 1';
    EXECUTE 'CREATE INDEX ON ' || quote_ident(_tablename) || ' (cf_initiation_eligible) WHERE cf_initiation_eligible = 1';
    EXECUTE 'CREATE INDEX ON ' || quote_ident(_tablename) || ' (ebf_eligible) WHERE ebf_eligible = 1';
    EXECUTE 'CREATE INDEX ON ' || quote_ident(_tablename) || ' (pnc_eligible) WHERE pnc_eligible = 1';

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
      'cf_in_month = COALESCE(agg.comp_feeding_latest, 0), ' ||
      'cf_diet_diversity = COALESCE(agg.diet_diversity, 0), ' ||
      'cf_diet_quantity = COALESCE(agg.diet_quantity, 0), ' ||
      'cf_handwashing = COALESCE(agg.hand_wash, 0), ' ||
      'cf_demo = COALESCE(agg.demo_comp_feeding, 0), ' ||
      'counsel_pediatric_ifa = COALESCE(agg.counselled_pediatric_ifa, 0) , ' ||
      'counsel_comp_feeding_vid = COALESCE(agg.play_comp_feeding_vid, 0)  ' ||
    'FROM ' || quote_ident(_agg_complementary_feeding_table) || ' agg ' ||
    'WHERE chm_monthly.case_id = agg.case_id AND chm_monthly.cf_eligible = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
      'cf_initiation_in_month = COALESCE(agg.comp_feeding_ever, 0) ' ||
    'FROM ' || quote_ident(_agg_complementary_feeding_table) || ' agg ' ||
    'WHERE chm_monthly.case_id = agg.case_id AND chm_monthly.cf_initiation_eligible = 1 AND agg.month = ' || quote_literal(_start_date);

    -- This will end up being a seq scan on the tasks table. Ok for now, but will likely need to be optimized with temp table later
    -- Can check documentation on immunizations: https://confluence.dimagi.com/display/ICDS/Due+List+Details
    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
      'immunization_in_month = 1 ' ||
    'FROM ' || quote_ident(_ucr_child_tasks_table) || ' ut ' ||
    'WHERE chm_monthly.case_id = ut.child_health_case_id AND (' ||
      'ut.due_list_date_1g_dpt_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_2g_dpt_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_3g_dpt_3 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_5g_dpt_booster BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_5g_dpt_booster1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_7gdpt_booster_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_0g_hep_b_0 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_1g_hep_b_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_2g_hep_b_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_3g_hep_b_3 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_3g_ipv BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_4g_je_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_5g_je_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_5g_measles_booster BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_4g_measles BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_1g_penta_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_2g_penta_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_3g_penta_3 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_1g_rv_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_2g_rv_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_3g_rv_3 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_4g_vit_a_1 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_5g_vit_a_2 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_6g_vit_a_3 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_6g_vit_a_4 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_6g_vit_a_5 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_6g_vit_a_6 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_6g_vit_a_7 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_6g_vit_a_8 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' OR ' ||
      'ut.due_list_date_7g_vit_a_9 BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) ||
    ') ';

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
      'days_ration_given_child = agg.days_ration_given_child  ' ||
    'FROM ' || quote_ident(_agg_thr_form_table) || ' agg ' ||
    'WHERE chm_monthly.case_id = agg.case_id AND chm_monthly.valid_in_month = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
      'zscore_grading_hfa = agg.zscore_grading_hfa, ' ||
      'zscore_grading_hfa_recorded_in_month = CASE WHEN (date_trunc(' || quote_literal('MONTH') || ', agg.zscore_grading_hfa_last_recorded) = ' || quote_literal(_start_date) || ') THEN 1 ELSE 0 END, ' ||
      'zscore_grading_wfh = agg.zscore_grading_wfh, ' ||
      'zscore_grading_wfh_recorded_in_month = CASE WHEN (date_trunc(' || quote_literal('MONTH') || ', agg.zscore_grading_wfh_last_recorded) = ' || quote_literal(_start_date) || ') THEN 1 ELSE 0 END, ' ||
      'muac_grading = agg.muac_grading, ' ||
      'muac_grading_recorded_in_month = CASE WHEN (date_trunc(' || quote_literal('MONTH') || ', agg.muac_grading_last_recorded) = ' || quote_literal(_start_date) || ') THEN 1 ELSE 0 END ' ||
    'FROM ' || quote_ident(_agg_gm_form_table) || ' agg ' ||
    'WHERE chm_monthly.case_id = agg.case_id AND chm_monthly.valid_in_month = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
      'counsel_increase_food_bf = COALESCE(agg.counsel_increase_food_bf, 0), ' ||
      'counsel_manage_breast_problems = COALESCE(agg.counsel_breast, 0), ' ||
      'counsel_skin_to_skin = COALESCE(agg.skin_to_skin, 0) ' ||
    'FROM ' || quote_ident(_agg_pnc_form_table) || ' agg ' ||
    'WHERE chm_monthly.case_id = agg.case_id AND chm_monthly.pnc_eligible = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
      'ebf_in_month = COALESCE(agg.is_ebf, 0), ' ||
      'ebf_drinking_liquid = GREATEST(agg.water_or_milk, agg.other_milk_to_child, agg.tea_other, 0), ' ||
      'ebf_eating = COALESCE(agg.eating, 0), ' ||
      'ebf_not_breastfeeding_reason = agg.not_breastfeeding, ' ||
      'counsel_ebf = GREATEST(agg.counsel_exclusive_bf, agg.counsel_only_milk, 0), ' ||
      'counsel_adequate_bf = COALESCE(agg.counsel_adequate_bf, 0), ' ||
      'ebf_no_info_recorded = CASE WHEN (date_trunc(' || quote_literal('MONTH') || ', agg.latest_time_end_processed) = ' || quote_literal(_start_date) || ') THEN 0 ELSE 1 END ' ||
    'FROM ' || quote_ident(_agg_pnc_form_table) || ' agg ' ||
    'WHERE chm_monthly.case_id = agg.case_id AND chm_monthly.ebf_eligible = 1 AND agg.month = ' || quote_literal(_start_date);

    EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id, case_id)';

    EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' chm_monthly SET ' ||
        'person_name = ucr_case.person_name, ' ||
        'mother_name = ucr_case.mother_name  ' ||
    'FROM ' || quote_ident(_ucr_child_health_cases_table) || ' ucr_case ' ||
    'WHERE chm_monthly.case_id = ucr_case.case_id AND chm_monthly.month = ' || quote_literal(_start_date);
END;
$BODY$
LANGUAGE plpgsql;
