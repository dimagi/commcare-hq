-- Aggregate a single table for the AWC
-- Depends on generation of other tables
CREATE OR REPLACE FUNCTION aggregate_awc_data(date) RETURNS VOID AS
$BODY$
DECLARE
  _start_date date;
  _end_date date;
  _previous_month_date date;
  _tablename1 text;
  _tablename2 text;
  _tablename3 text;
  _tablename4 text;
  _tablename5 text;
  _child_health_tablename text;
  _ccs_record_tablename text;
  _ccs_record_monthly_tablename text;
  _child_health_monthly_tablename text;
  _daily_attendance_tablename text;
  _awc_location_tablename text;
  _usage_tablename text;
  _infra_tablename text;
  _household_tablename text;
  _person_tablename text;
  _all_text text;
  _null_value text;
  _rollup_text text;
  _rollup_text2 text;
  _yes_text text;
  _no_text text;
  _female text;
  _month_start_6m date;
  _month_end_6yr date;
  _month_start_11yr date;
  _month_end_11yr date;
  _month_start_15yr date;
  _month_end_15yr date;
  _month_start_18yr date;
  _month_end_49yr date;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _end_date = (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 day')::DATE;
  _previous_month_date = (date_trunc('MONTH', _start_date) + INTERVAL '- 1 MONTH')::DATE;
  _month_start_6m = (_start_date + INTERVAL ' - 6 MONTHS')::DATE;
  _month_end_6yr = (_end_date + INTERVAL ' - 6 YEAR')::DATE;
  _month_start_11yr = (_start_date + INTERVAL ' - 11 YEAR')::DATE;
  _month_end_11yr = (_end_date + INTERVAL ' - 11 YEAR')::DATE;
  _month_start_15yr = (_start_date + INTERVAL ' - 15 YEAR')::DATE;
  _month_end_15yr = (_end_date + INTERVAL ' - 15 YEAR')::DATE;
  _month_start_18yr = (_start_date + INTERVAL ' - 18 YEAR')::DATE;
  _month_end_49yr = (_end_date + INTERVAL ' - 49 YEAR')::DATE;
  _all_text = 'All';
  _null_value = NULL;
  _yes_text = 'yes';
  _no_text = 'no';
  _female = 'F';
  _tablename1 := 'agg_awc' || '_' || _start_date || '_1';
  _tablename2 := 'agg_awc' || '_' || _start_date || '_2';
  _tablename3 := 'agg_awc' || '_' || _start_date || '_3';
  _tablename4 := 'agg_awc' || '_' || _start_date || '_4';
  _tablename5 := 'agg_awc' || '_' || _start_date || '_5';
  _child_health_tablename := 'agg_child_health';
  _ccs_record_tablename := 'agg_ccs_record';
  _ccs_record_monthly_tablename := 'ccs_record_monthly' || '_' || _start_date;
  _child_health_monthly_tablename := 'child_health_monthly' || '_' || _start_date;
  _daily_attendance_tablename := 'daily_attendance' || '_' || _start_date;
  _infra_tablename := 'icds_dashboard_infrastructure_forms';
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('awc_location') INTO _awc_location_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('usage') INTO _usage_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('household') INTO _household_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('person') INTO _person_tablename;

  -- Setup base locations and month
  EXECUTE 'INSERT INTO ' || quote_ident(_tablename5) ||
    ' (state_id, district_id, block_id, supervisor_id, awc_id, month, num_awcs, ' ||
    'is_launched, aggregation_level) ' ||
    '(SELECT ' ||
      'state_id, ' ||
      'district_id, ' ||
      'block_id, ' ||
      'supervisor_id, ' ||
      'doc_id AS awc_id, ' ||
      quote_literal(_start_date) || ', ' ||
      '1, ' ||
      quote_literal(_no_text) || ', ' ||
      '5 ' ||
    'FROM ' || quote_ident(_awc_location_tablename) ||')';

  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx1') || ' ON ' || quote_ident(_tablename5) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx5') || ' ON ' || quote_ident(_tablename5) || '(awc_id)';

  -- Aggregate daily attendance table.
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'awc_days_open = ut.awc_days_open, ' ||
    'awc_num_open = ut.awc_num_open, ' ||
    'awc_days_pse_conducted = ut.awc_days_pse_conducted ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'sum(awc_open_count) AS awc_days_open, ' ||
    'CASE WHEN (sum(awc_open_count) > 0) THEN 1 ELSE 0 END AS awc_num_open, ' ||
    'sum(pse_conducted) as awc_days_pse_conducted '
    'FROM ' || quote_ident(_daily_attendance_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

  -- Aggregate monthly child health table
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_child_health = ut.cases_child_health, ' ||
    'cases_child_health_all = ut.cases_child_health_all, ' ||
    'wer_weighed = ut.wer_weighed, ' ||
    'wer_eligible = ut.wer_eligible, ' ||
    'cases_person_beneficiary_v2 = ut.cases_child_health ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'sum(valid_in_month) AS cases_child_health, ' ||
    'sum(valid_all_registered_in_month) AS cases_child_health_all, ' ||
    'sum(nutrition_status_weighed) AS wer_weighed, ' ||
    'sum(wer_eligible) AS wer_eligible ' ||
    'FROM ' || quote_ident(_child_health_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' AND aggregation_level = 5 GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

  -- Aggregate monthly ccs record table
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_ccs_pregnant = ut.cases_ccs_pregnant, ' ||
    'cases_ccs_lactating = ut.cases_ccs_lactating, ' ||
    'cases_ccs_pregnant_all = ut.cases_ccs_pregnant_all, ' ||
    'cases_ccs_lactating_all = ut.cases_ccs_lactating_all, ' ||
    'cases_person_beneficiary_v2 = COALESCE(cases_person_beneficiary_v2, 0) + ut.cases_ccs_pregnant + ut.cases_ccs_lactating ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'sum(pregnant) AS cases_ccs_pregnant, ' ||
    'sum(lactating) AS cases_ccs_lactating, ' ||
    'sum(pregnant_all) AS cases_ccs_pregnant_all, ' ||
    'sum(lactating_all) AS cases_ccs_lactating_all ' ||
    'FROM ' || quote_ident(_ccs_record_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' AND aggregation_level = 5 GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

  -- Aggregate household table
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_household = ut.cases_household ' ||
  'FROM (SELECT ' ||
    'owner_id, ' ||
    'sum(open_count) AS cases_household ' ||
    'FROM ' || quote_ident(_household_tablename) || ' ' ||
    'GROUP BY owner_id) ut ' ||
  'WHERE ut.owner_id = agg_awc.awc_id';

  -- Aggregate person table
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_person = ut.cases_person, ' ||
    'cases_person_all = ut.cases_person_all, ' ||
    'cases_person_adolescent_girls_11_14 = ut.cases_person_adolescent_girls_11_14, ' ||
    'cases_person_adolescent_girls_11_14_all = ut.cases_person_adolescent_girls_11_14_all, ' ||
    'cases_person_adolescent_girls_15_18 = ut.cases_person_adolescent_girls_15_18, ' ||
    'cases_person_adolescent_girls_15_18_all = ut.cases_person_adolescent_girls_15_18_all, ' ||
    'cases_person_referred = ut.cases_person_referred ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'sum(seeking_services) AS cases_person, ' ||
    'sum(count) AS cases_person_all, ' ||
    'sum(CASE WHEN ' || quote_literal(_month_end_11yr) || ' > dob AND ' || quote_literal(_month_start_15yr) || ' <= dob' || ' AND sex = ' || quote_literal(_female) || ' THEN seeking_services ELSE 0 END) as cases_person_adolescent_girls_11_14, ' ||
    'sum(CASE WHEN ' || quote_literal(_month_end_11yr) || ' > dob AND ' || quote_literal(_month_start_15yr) || ' <= dob' || ' AND sex = ' || quote_literal(_female) || ' THEN 1 ELSE 0 END) as cases_person_adolescent_girls_11_14_all, ' ||
    'sum(CASE WHEN ' || quote_literal(_month_end_15yr) || ' > dob AND ' || quote_literal(_month_start_18yr) || ' <= dob' || ' AND sex = ' || quote_literal(_female) || ' THEN seeking_services ELSE 0 END) as cases_person_adolescent_girls_15_18, ' ||
    'sum(CASE WHEN ' || quote_literal(_month_end_15yr) || ' > dob AND ' || quote_literal(_month_start_18yr) || ' <= dob' || ' AND sex = ' || quote_literal(_female) || ' THEN 1 ELSE 0 END) as cases_person_adolescent_girls_15_18_all, ' ||
    'sum(CASE WHEN last_referral_date BETWEEN ' || quote_literal(_start_date) || ' AND ' || quote_literal(_end_date) || ' THEN 1 ELSE 0 END) as cases_person_referred '
    'FROM ' || quote_ident(_person_tablename) || ' ' ||
    'WHERE (opened_on <= ' || quote_literal(_end_date) || ' AND (closed_on IS NULL OR closed_on >= ' || quote_literal(_start_date) || ' )) ' ||
    'GROUP BY awc_id) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

  -- Update number of children immunized
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_person_has_aadhaar_v2 = ut.child_has_aadhar, ' ||
    'num_children_immunized = ut.num_children_immunized ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'sum(has_aadhar_id) as child_has_aadhar, ' ||
    'sum(immunization_in_month) AS num_children_immunized ' ||
    'FROM ' || quote_ident(_child_health_monthly_tablename) || ' ' ||
    'WHERE valid_in_month = 1' ||
    'GROUP BY awc_id) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

  -- Update number anc visits
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'num_anc_visits = ut.num_anc_visits, ' ||
    'cases_person_has_aadhaar_v2 = COALESCE(cases_person_has_aadhaar_v2, 0) + ut.ccs_has_aadhar ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'sum(anc_in_month) AS num_anc_visits, ' ||
    'sum(has_aadhar_id) AS ccs_has_aadhar ' ||
    'FROM ' || quote_ident(_ccs_record_monthly_tablename) || ' ' ||
    'WHERE pregnant = 1 OR lactating = 1 ' ||
    'GROUP BY awc_id) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

  -- Aggregate data from usage table
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'usage_num_pse = ut.usage_num_pse, ' ||
    'usage_num_gmp = ut.usage_num_gmp, ' ||
    'usage_num_thr = ut.usage_num_thr, ' ||
    'usage_num_hh_reg = ut.usage_num_hh_reg, ' ||
    'is_launched = ut.is_launched, ' ||
    'num_launched_states = ut.num_launched_awcs, ' ||
    'num_launched_districts = ut.num_launched_awcs, ' ||
    'num_launched_blocks = ut.num_launched_awcs, ' ||
    'num_launched_supervisors = ut.num_launched_awcs, ' ||
    'num_launched_awcs = ut.num_launched_awcs, ' ||
    'usage_num_add_person = ut.usage_num_add_person, ' ||
    'usage_num_add_pregnancy = ut.usage_num_add_pregnancy, ' ||
    'usage_num_home_visit = ut.usage_num_home_visit, ' ||
    'usage_num_bp_tri1 = ut.usage_num_bp_tri1, ' ||
    'usage_num_bp_tri2 = ut.usage_num_bp_tri2, ' ||
    'usage_num_bp_tri3 = ut.usage_num_bp_tri3, ' ||
    'usage_num_pnc = ut.usage_num_pnc, ' ||
    'usage_num_ebf = ut.usage_num_ebf, ' ||
    'usage_num_cf = ut.usage_num_cf, ' ||
    'usage_num_delivery = ut.usage_num_delivery, ' ||
    'usage_awc_num_active = ut.usage_awc_num_active, ' ||
    'usage_num_due_list_ccs = ut.usage_num_due_list_ccs, ' ||
    'usage_num_due_list_child_health = ut.usage_num_due_list_child_health ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'sum(pse) AS usage_num_pse, ' ||
    'sum(gmp) AS usage_num_gmp, ' ||
    'sum(thr) AS usage_num_thr, ' ||
    'sum(add_household) AS usage_num_hh_reg, ' ||
    'CASE WHEN sum(add_household) > 0 THEN ' || quote_literal(_yes_text) || ' ELSE ' || quote_literal(_no_text) || ' END as is_launched, '
    'CASE WHEN sum(add_household) > 0 THEN 1 ELSE 0 END as num_launched_awcs, '
    'sum(add_person) AS usage_num_add_person, ' ||
    'sum(add_pregnancy) AS usage_num_add_pregnancy, ' ||
    'sum(home_visit) AS usage_num_home_visit, ' ||
    'sum(bp_tri1) AS usage_num_bp_tri1, ' ||
    'sum(bp_tri2) AS usage_num_bp_tri2, ' ||
    'sum(bp_tri3) AS usage_num_bp_tri3, ' ||
    'sum(pnc) AS usage_num_pnc, ' ||
    'sum(ebf) AS usage_num_ebf, ' ||
    'sum(cf) AS usage_num_cf, ' ||
    'sum(delivery) AS usage_num_delivery, ' ||
    'CASE WHEN (sum(due_list_ccs) + sum(due_list_child) + sum(pse) + sum(gmp) + sum(thr) + sum(home_visit) + sum(add_pregnancy) + sum(add_household)) >= 15 THEN 1 ELSE 0 END AS usage_awc_num_active, ' ||
    'sum(due_list_ccs) AS usage_num_due_list_ccs, ' ||
    'sum(due_list_child) AS usage_num_due_list_child_health ' ||
    'FROM ' || quote_ident(_usage_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

  -- Update num launched AWCs based on previous month as well
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
     'is_launched = ' || quote_literal(_yes_text) || ', ' ||
     'num_launched_awcs = 1 ' ||
    'FROM (SELECT DISTINCT(awc_id) ' ||
       'FROM agg_awc ' ||
  'WHERE month = ' || quote_literal(_previous_month_date) || ' AND num_launched_awcs > 0 AND aggregation_level = 5) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

  -- Get latest infrastructure data
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'infra_last_update_date = ut.infra_last_update_date, ' ||
    'infra_type_of_building = ut.infra_type_of_building, ' ||
    'infra_clean_water = ut.infra_clean_water, ' ||
    'infra_functional_toilet = ut.infra_functional_toilet, ' ||
    'infra_baby_weighing_scale = ut.infra_baby_weighing_scale, ' ||
    'infra_adult_weighing_scale = ut.infra_adult_weighing_scale, ' ||
    'infra_infant_weighing_scale = ut.infra_infant_weighing_scale, ' ||
    'infra_cooking_utensils = ut.infra_cooking_utensils, ' ||
    'infra_medicine_kits = ut.infra_medicine_kits, ' ||
    'infra_adequate_space_pse = ut.infra_adequate_space_pse, ' ||
    'electricity_awc = ut.electricity_awc, ' ||
    'infantometer = ut.infantometer, ' ||
    'stadiometer = ut.stadiometer ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'latest_time_end_processed::date AS infra_last_update_date, ' ||
    'CASE ' ||
      'WHEN awc_building = 1 THEN ' || quote_literal('pucca') || ' ' ||
      'WHEN awc_building = 2 THEN ' || quote_literal('semi_pucca') || ' ' ||
      'WHEN awc_building = 3 THEN ' || quote_literal('kuccha') || ' ' ||
      'WHEN awc_building = 4 THEN ' || quote_literal('partial_covered_space') || ' ' ||
    'ELSE NULL END AS infra_type_of_building, ' ||
    'CASE WHEN source_drinking_water IN (1, 2, 3) THEN 1 ELSE 0 END AS infra_clean_water, ' ||
    'toilet_functional AS infra_functional_toilet, ' ||
    'baby_scale_usable AS infra_baby_weighing_scale, ' ||
    'GREATEST(adult_scale_available, adult_scale_usable, 0) AS infra_adult_weighing_scale, ' ||
    'GREATEST(baby_scale_available, flat_scale_available, baby_scale_usable, 0) AS infra_infant_weighing_scale, ' ||
    'cooking_utensils_usable AS infra_cooking_utensils, ' ||
    'medicine_kits_usable AS infra_medicine_kits, ' ||
    'CASE WHEN adequate_space_pse = 1 THEN 1 ELSE 0 END AS infra_adequate_space_pse, ' ||
    'electricity_awc AS electricity_awc, ' ||
    'infantometer_usable AS infantometer, ' ||
    'stadiometer_usable AS stadiometer ' ||
    'FROM ' || quote_ident(_infra_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ') ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';
    -- could possibly add multicol indexes to make order by faster?

  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET num_awc_infra_last_update = ' ||
   'CASE WHEN infra_last_update_date IS NOT NULL AND ' ||
     quote_literal(_month_start_6m) || ' < infra_last_update_date THEN 1 ELSE 0 END';

  -- Roll Up by Location
  _rollup_text =   'sum(num_awcs), ' ||
    'sum(awc_days_open), ' ||
    'sum(awc_num_open), ' ||
    'sum(wer_weighed), ' ||
    'sum(wer_eligible), ' ||
    'sum(cases_ccs_pregnant), ' ||
    'sum(cases_ccs_lactating), ' ||
    'sum(cases_child_health), ' ||
    'sum(usage_num_pse), ' ||
    'sum(usage_num_gmp), ' ||
    'sum(usage_num_thr), ' ||
    'sum(usage_num_home_visit), ' ||
    'sum(usage_num_bp_tri1), ' ||
    'sum(usage_num_bp_tri2), ' ||
    'sum(usage_num_bp_tri3), ' ||
    'sum(usage_num_pnc), ' ||
    'sum(usage_num_ebf), ' ||
    'sum(usage_num_cf), ' ||
    'sum(usage_num_delivery), ' ||
    'sum(usage_num_due_list_ccs), ' ||
    'sum(usage_num_due_list_child_health), ' ||
    'sum(usage_awc_num_active), ' ||
    quote_nullable(_null_value) || ', ' ||
    quote_nullable(_null_value) || ', ' ||
    'sum(infra_clean_water), ' ||
    'sum(infra_functional_toilet), ' ||
    'sum(infra_baby_weighing_scale), ' ||
    'sum(infra_adult_weighing_scale), ' ||
    'sum(infra_cooking_utensils), ' ||
    'sum(infra_medicine_kits), ' ||
    'sum(infra_adequate_space_pse), ' ||
    'sum(usage_num_hh_reg), ' ||
    'sum(usage_num_add_person), ' ||
    'sum(usage_num_add_pregnancy), ' ||
    quote_literal(_yes_text) || ', ';

    _rollup_text2 = 'sum(cases_household), ' ||
        'sum(cases_person), ' ||
        'sum(cases_person_all), ' ||
        'sum(cases_ccs_pregnant_all), ' ||
        'sum(cases_ccs_lactating_all), ' ||
        'sum(cases_child_health_all), ' ||
        'sum(cases_person_adolescent_girls_11_14), ' ||
        'sum(cases_person_adolescent_girls_15_18), ' ||
        'sum(cases_person_adolescent_girls_11_14_all), ' ||
        'sum(cases_person_adolescent_girls_15_18_all), ' ||
        'sum(infra_infant_weighing_scale), ' ||
        quote_nullable(_null_value) || ', ' ||
        quote_nullable(_null_value) || ', ' ||
        'sum(num_awc_infra_last_update), ' ||
        'sum(cases_person_has_aadhaar_v2 ), ' ||
        'sum(cases_person_beneficiary_v2), ' ||
        'COALESCE(sum(electricity_awc), 0), ' ||
        'COALESCE(sum(infantometer), 0), ' ||
        'COALESCE(sum(stadiometer), 0), ' ||
        'COALESCE(sum(num_anc_visits), 0), ' ||
        'COALESCE(sum(num_children_immunized), 0) ';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'num_awcs, ' ||
    'awc_days_open, ' ||
    'awc_num_open, ' ||
    'wer_weighed, ' ||
    'wer_eligible, ' ||
    'cases_ccs_pregnant, ' ||
    'cases_ccs_lactating, ' ||
    'cases_child_health, ' ||
    'usage_num_pse, ' ||
    'usage_num_gmp, ' ||
    'usage_num_thr, ' ||
    'usage_num_home_visit, ' ||
    'usage_num_bp_tri1, ' ||
    'usage_num_bp_tri2, ' ||
    'usage_num_bp_tri3, ' ||
    'usage_num_pnc, ' ||
    'usage_num_ebf, ' ||
    'usage_num_cf, ' ||
    'usage_num_delivery, ' ||
    'usage_num_due_list_ccs, ' ||
    'usage_num_due_list_child_health, ' ||
    'usage_awc_num_active, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'aggregation_level, ' ||
    'num_launched_states, ' ||
    'num_launched_districts, ' ||
    'num_launched_blocks, ' ||
    'num_launched_supervisors, ' ||
    'num_launched_awcs, ' ||
    'cases_household, ' ||
    'cases_person, ' ||
    'cases_person_all, ' ||
    'cases_ccs_pregnant_all, ' ||
    'cases_ccs_lactating_all, ' ||
    'cases_child_health_all, ' ||
    'cases_person_adolescent_girls_11_14, ' ||
    'cases_person_adolescent_girls_15_18, ' ||
    'cases_person_adolescent_girls_11_14_all, ' ||
    'cases_person_adolescent_girls_15_18_all, ' ||
    'infra_infant_weighing_scale, ' ||
    'cases_person_referred, ' ||
    'awc_days_pse_conducted, ' ||
    'num_awc_infra_last_update, ' ||
    'cases_person_has_aadhaar_v2, ' ||
    'cases_person_beneficiary_v2, ' ||
    'electricity_awc, ' ||
    'infantometer, ' ||
    'stadiometer, ' ||
    'num_anc_visits, ' ||
    'num_children_immunized ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    _rollup_text ||
    '4, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename5) || ' ' ||
    'GROUP BY state_id, district_id, block_id, supervisor_id, month)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx1') || ' ON ' || quote_ident(_tablename4) || '(state_id, district_id, block_id, supervisor_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx2') || ' ON ' || quote_ident(_tablename4) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx3') || ' ON ' || quote_ident(_tablename4) || '(block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx4') || ' ON ' || quote_ident(_tablename4) || '(supervisor_id)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'num_awcs, ' ||
    'awc_days_open, ' ||
    'awc_num_open, ' ||
    'wer_weighed, ' ||
    'wer_eligible, ' ||
    'cases_ccs_pregnant, ' ||
    'cases_ccs_lactating, ' ||
    'cases_child_health, ' ||
    'usage_num_pse, ' ||
    'usage_num_gmp, ' ||
    'usage_num_thr, ' ||
    'usage_num_home_visit, ' ||
    'usage_num_bp_tri1, ' ||
    'usage_num_bp_tri2, ' ||
    'usage_num_bp_tri3, ' ||
    'usage_num_pnc, ' ||
    'usage_num_ebf, ' ||
    'usage_num_cf, ' ||
    'usage_num_delivery, ' ||
    'usage_num_due_list_ccs, ' ||
    'usage_num_due_list_child_health, ' ||
    'usage_awc_num_active, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'aggregation_level, ' ||
    'num_launched_states, ' ||
    'num_launched_districts, ' ||
    'num_launched_blocks, ' ||
    'num_launched_supervisors, ' ||
    'num_launched_awcs, ' ||
    'cases_household, ' ||
    'cases_person, ' ||
    'cases_person_all, ' ||
    'cases_ccs_pregnant_all, ' ||
    'cases_ccs_lactating_all, ' ||
    'cases_child_health_all, ' ||
    'cases_person_adolescent_girls_11_14, ' ||
    'cases_person_adolescent_girls_15_18, ' ||
    'cases_person_adolescent_girls_11_14_all, ' ||
    'cases_person_adolescent_girls_15_18_all, ' ||
    'infra_infant_weighing_scale, ' ||
    'cases_person_referred, ' ||
    'awc_days_pse_conducted, ' ||
    'num_awc_infra_last_update, ' ||
    'cases_person_has_aadhaar_v2, ' ||
    'cases_person_beneficiary_v2, ' ||
    'electricity_awc, ' ||
    'infantometer, ' ||
    'stadiometer, ' ||
    'num_anc_visits, ' ||
    'num_children_immunized ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    _rollup_text ||
    '3, ' ||
    'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_supervisors), ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename4) || ' ' ||
    'GROUP BY state_id, district_id, block_id, month)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx1') || ' ON ' || quote_ident(_tablename3) || '(state_id, district_id, block_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx2') || ' ON ' || quote_ident(_tablename3) || '(district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx3') || ' ON ' || quote_ident(_tablename3) || '(block_id)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'num_awcs, ' ||
    'awc_days_open, ' ||
    'awc_num_open, ' ||
    'wer_weighed, ' ||
    'wer_eligible, ' ||
    'cases_ccs_pregnant, ' ||
    'cases_ccs_lactating, ' ||
    'cases_child_health, ' ||
    'usage_num_pse, ' ||
    'usage_num_gmp, ' ||
    'usage_num_thr, ' ||
    'usage_num_home_visit, ' ||
    'usage_num_bp_tri1, ' ||
    'usage_num_bp_tri2, ' ||
    'usage_num_bp_tri3, ' ||
    'usage_num_pnc, ' ||
    'usage_num_ebf, ' ||
    'usage_num_cf, ' ||
    'usage_num_delivery, ' ||
    'usage_num_due_list_ccs, ' ||
    'usage_num_due_list_child_health, ' ||
    'usage_awc_num_active, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'aggregation_level, ' ||
    'num_launched_states, ' ||
    'num_launched_districts, ' ||
    'num_launched_blocks, ' ||
    'num_launched_supervisors, ' ||
    'num_launched_awcs, ' ||
    'cases_household, ' ||
    'cases_person, ' ||
    'cases_person_all, ' ||
    'cases_ccs_pregnant_all, ' ||
    'cases_ccs_lactating_all, ' ||
    'cases_child_health_all, ' ||
    'cases_person_adolescent_girls_11_14, ' ||
    'cases_person_adolescent_girls_15_18, ' ||
    'cases_person_adolescent_girls_11_14_all, ' ||
    'cases_person_adolescent_girls_15_18_all, ' ||
    'infra_infant_weighing_scale, ' ||
    'cases_person_referred, ' ||
    'awc_days_pse_conducted, ' ||
    'num_awc_infra_last_update, ' ||
    'cases_person_has_aadhaar_v2, ' ||
    'cases_person_beneficiary_v2, ' ||
    'electricity_awc, ' ||
    'infantometer, ' ||
    'stadiometer, ' ||
    'num_anc_visits, ' ||
    'num_children_immunized ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    'district_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    _rollup_text ||
    '2, ' ||
    'CASE WHEN (sum(num_launched_blocks) > 0) THEN 1 ELSE 0 END, ' ||
    'CASE WHEN (sum(num_launched_blocks) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_blocks), ' ||
    'sum(num_launched_supervisors), ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename3) || ' ' ||
    'GROUP BY state_id, district_id, month)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx1') || ' ON ' || quote_ident(_tablename2) || '(state_id, district_id)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx2') || ' ON ' || quote_ident(_tablename2) || '(district_id)';

  EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || ' ' ||
    '(' ||
    'state_id, ' ||
    'district_id, ' ||
    'block_id, ' ||
    'supervisor_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'num_awcs, ' ||
    'awc_days_open, ' ||
    'awc_num_open, ' ||
    'wer_weighed, ' ||
    'wer_eligible, ' ||
    'cases_ccs_pregnant, ' ||
    'cases_ccs_lactating, ' ||
    'cases_child_health, ' ||
    'usage_num_pse, ' ||
    'usage_num_gmp, ' ||
    'usage_num_thr, ' ||
    'usage_num_home_visit, ' ||
    'usage_num_bp_tri1, ' ||
    'usage_num_bp_tri2, ' ||
    'usage_num_bp_tri3, ' ||
    'usage_num_pnc, ' ||
    'usage_num_ebf, ' ||
    'usage_num_cf, ' ||
    'usage_num_delivery, ' ||
    'usage_num_due_list_ccs, ' ||
    'usage_num_due_list_child_health, ' ||
    'usage_awc_num_active, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'aggregation_level, ' ||
    'num_launched_states, ' ||
    'num_launched_districts, ' ||
    'num_launched_blocks, ' ||
    'num_launched_supervisors, ' ||
    'num_launched_awcs, ' ||
    'cases_household, ' ||
    'cases_person, ' ||
    'cases_person_all, ' ||
    'cases_ccs_pregnant_all, ' ||
    'cases_ccs_lactating_all, ' ||
    'cases_child_health_all, ' ||
    'cases_person_adolescent_girls_11_14, ' ||
    'cases_person_adolescent_girls_15_18, ' ||
    'cases_person_adolescent_girls_11_14_all, ' ||
    'cases_person_adolescent_girls_15_18_all, ' ||
    'infra_infant_weighing_scale, ' ||
    'cases_person_referred, ' ||
    'awc_days_pse_conducted, ' ||
    'num_awc_infra_last_update, ' ||
    'cases_person_has_aadhaar_v2, ' ||
    'cases_person_beneficiary_v2, ' ||
    'electricity_awc, ' ||
    'infantometer, ' ||
    'stadiometer, ' ||
    'num_anc_visits, ' ||
    'num_children_immunized ' ||
    ')' ||
    '(SELECT ' ||
    'state_id, ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    quote_literal(_all_text) || ', ' ||
    'month, ' ||
    _rollup_text ||
    '1, ' ||
    'CASE WHEN (sum(num_launched_districts) > 0) THEN 1 ELSE 0 END, ' ||
    'sum(num_launched_districts), ' ||
    'sum(num_launched_blocks), ' ||
    'sum(num_launched_supervisors), ' ||
    'sum(num_launched_awcs), ' ||
    _rollup_text2 ||
    'FROM ' || quote_ident(_tablename2) || ' ' ||
    'GROUP BY state_id, month)';
  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx1') || ' ON ' || quote_ident(_tablename1) || '(state_id)';

END;
$BODY$
LANGUAGE plpgsql;
