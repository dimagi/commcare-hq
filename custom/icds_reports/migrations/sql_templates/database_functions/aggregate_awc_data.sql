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
  _vhnd_tablename text;
  _ls_tablename text;
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
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('daily_feeding') INTO _daily_attendance_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('awc_location') INTO _awc_location_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('usage') INTO _usage_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('vhnd') INTO _vhnd_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('awc_mgmt') INTO _ls_tablename;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('infrastructure') INTO _infra_tablename;
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

  -- Aggregate daily attendance table.  Not using monthly table as it doesn't have all indicators
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
    'wer_eligible = ut.wer_eligible ' ||
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
    'cases_ccs_lactating_all = ut.cases_ccs_lactating_all ' ||
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

  -- Update child_health cases_person_has_aadhaar and cases_person_beneficiary
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_person_has_aadhaar_v2 = ut.child_has_aadhar, ' ||
    'cases_person_beneficiary_v2 = ut.child_beneficiary, ' ||
    'num_children_immunized = ut.num_children_immunized ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'sum(has_aadhar_id) as child_has_aadhar, ' ||
    'count(*) as child_beneficiary, ' ||
    'sum(immunization_in_month) AS num_children_immunized ' ||
    'FROM ' || quote_ident(_child_health_monthly_tablename) || ' ' ||
    'WHERE valid_in_month = 1' ||
    'GROUP BY awc_id) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

  -- Update ccs_record cases_person_has_aadhaar and cases_person_beneficiary
  -- pregnant and lactating both imply that the case is open, alive and seeking services in the month
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_person_has_aadhaar_v2 = COALESCE(cases_person_has_aadhaar_v2, 0) + ut.ccs_has_aadhar, ' ||
    'cases_person_beneficiary_v2 = COALESCE(cases_person_beneficiary_v2, 0) + ut.ccs_beneficiary, ' ||
    'num_anc_visits = ut.num_anc_visits ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'sum(has_aadhar_id) as ccs_has_aadhar, ' ||
    'count(*) as ccs_beneficiary, ' ||
    'sum(anc_in_month) AS num_anc_visits ' ||
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
    'training_phase = ut.training_phase, ' ||
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
    'usage_num_due_list_child_health = ut.usage_num_due_list_child_health, ' ||
    'usage_time_pse = ut.usage_time_pse, ' ||
    'usage_time_gmp = ut.usage_time_gmp, ' ||
    'usage_time_bp = ut.usage_time_bp, ' ||
    'usage_time_pnc = ut.usage_time_pnc, ' ||
    'usage_time_ebf = ut.usage_time_ebf, ' ||
    'usage_time_cf = ut.usage_time_cf, ' ||
    'usage_time_of_day_pse = ut.usage_time_of_day_pse, ' ||
    'usage_time_of_day_home_visit = ut.usage_time_of_day_home_visit ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'sum(pse) AS usage_num_pse, ' ||
    'sum(gmp) AS usage_num_gmp, ' ||
    'sum(thr) AS usage_num_thr, ' ||
    'sum(add_household) AS usage_num_hh_reg, ' ||
    'CASE WHEN sum(add_household) > 0 THEN ' || quote_literal(_yes_text) || ' ELSE ' || quote_literal(_no_text) || ' END as is_launched, '
    'CASE WHEN sum(add_household) > 0 THEN 1 ELSE 0 END as num_launched_awcs, '
    'CASE WHEN sum(thr) > 0 THEN 4 WHEN (sum(due_list_ccs) + sum(due_list_child)) > 0 THEN 3 WHEN sum(add_pregnancy) > 0 THEN 2 WHEN sum(add_household) > 0 THEN 1 ELSE 0 END AS training_phase, '
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
    'sum(due_list_child) AS usage_num_due_list_child_health, ' ||
    'avg(pse_time) AS usage_time_pse, ' ||
    'avg(gmp_time) AS usage_time_gmp, ' ||
    'avg(bp_time) AS usage_time_bp, ' ||
    'avg(pnc_time) AS usage_time_pnc, ' ||
    'avg(ebf_time) AS usage_time_ebf, ' ||
    'avg(cf_time) AS usage_time_cf, ' ||
    'avg(pse_time_of_day::time) AS usage_time_of_day_pse, ' ||
    'avg(home_visit_time_of_day::time) AS usage_time_of_day_home_visit '
    'FROM ' || quote_ident(_usage_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

  -- Update num launched AWCs based on previous month as well
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
     'is_launched = ' || quote_literal(_yes_text) || ', ' ||
     'num_launched_awcs = 1 ' ||
    'FROM (SELECT DISTINCT(awc_id) ' ||
       'FROM agg_awc ' ||
  'WHERE month <= ' || quote_literal(_previous_month_date) || ' AND usage_num_hh_reg > 0 AND awc_id <> ' || quote_literal(_all_text) || ') ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

  -- Update training status based on the previous month as well
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
     'training_phase = ut.training_phase ' ||
    'FROM (SELECT awc_id, training_phase ' ||
       'FROM agg_awc ' ||
  'WHERE month = ' || quote_literal(_previous_month_date) || ' AND awc_id <> ' || quote_literal(_all_text) || ') ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id AND agg_awc.training_phase < ut.training_phase';

  -- Pass to calculate awc score and ranks and training status
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' SET (' ||
    'trained_phase_1, ' ||
    'trained_phase_2, ' ||
    'trained_phase_3, ' ||
    'trained_phase_4) = ' ||
  '(' ||
    'CASE WHEN training_phase = 1 THEN 1 ELSE 0 END, ' ||
    'CASE WHEN training_phase = 2 THEN 1 ELSE 0 END, ' ||
    'CASE WHEN training_phase = 3 THEN 1 ELSE 0 END, ' ||
    'CASE WHEN training_phase = 4 THEN 1 ELSE 0 END ' ||
  ')';

  -- Aggregate data from VHND table
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'vhnd_immunization = ut.vhnd_immunization, ' ||
    'vhnd_anc = ut.vhnd_anc, ' ||
    'vhnd_gmp = ut.vhnd_gmp, ' ||
    'vhnd_num_pregnancy = ut.vhnd_num_pregnancy, ' ||
    'vhnd_num_lactating = ut.vhnd_num_lactating, ' ||
    'vhnd_num_mothers_6_12 = ut.vhnd_num_mothers_6_12, ' ||
    'vhnd_num_mothers_12 = ut.vhnd_num_mothers_12, ' ||
    'vhnd_num_fathers = ut.vhnd_num_fathers ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'month, ' ||
    'sum(child_immu) AS vhnd_immunization, ' ||
    'sum(anc_today) AS vhnd_anc, ' ||
    'sum(vhnd_gmp) AS vhnd_gmp, ' ||
    'sum(vhnd_num_pregnant_women) AS vhnd_num_pregnancy, ' ||
    'sum(vhnd_num_lactating_women) AS vhnd_num_lactating, ' ||
    'sum(vhnd_num_mothers_6_12) AS vhnd_num_mothers_6_12, ' ||
    'sum(vhnd_num_mothers_12) AS vhnd_num_mothers_12, ' ||
    'sum(vhnd_num_fathers) AS vhnd_num_fathers '
    'FROM ' || quote_ident(_vhnd_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

  -- Aggregate data from LS supervision table
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'ls_supervision_visit = ut.ls_supervision_visit, ' ||
    'ls_num_supervised = ut.ls_num_supervised, ' ||
    'ls_awc_location_lat = ut.ls_awc_location_lat, ' ||
    'ls_awc_location_long = ut.ls_awc_location_long, ' ||
    'ls_awc_present = ut.ls_awc_present, ' ||
    'ls_awc_open = ut.ls_awc_open, ' ||
    'ls_awc_not_open_aww_not_available = ut.ls_awc_not_open_aww_not_available, ' ||
    'ls_awc_not_open_closed_early = ut.ls_awc_not_open_closed_early, ' ||
    'ls_awc_not_open_holiday = ut.ls_awc_not_open_holiday, ' ||
    'ls_awc_not_open_unknown = ut.ls_awc_not_open_unknown, ' ||
    'ls_awc_not_open_other = ut.ls_awc_not_open_other ' ||
  'FROM (SELECT ' ||
    'awc_id AS awc_id, ' ||
    'month, ' ||
    'sum(count) AS ls_supervision_visit, ' ||
    'CASE WHEN sum(count) > 0 THEN 1 ELSE 0 END AS ls_num_supervised, ' ||
    'avg(awc_location_lat) AS ls_awc_location_lat, ' ||
    'avg(awc_location_long) AS ls_awc_location_long, ' ||
    'sum(aww_present) AS ls_awc_present, ' ||
    'sum(awc_open) AS ls_awc_open, ' ||
    'sum(awc_not_open_aww_not_available) AS ls_awc_not_open_aww_not_available, ' ||
    'sum(awc_not_open_closed_early) AS ls_awc_not_open_closed_early, ' ||
    'sum(awc_not_open_holiday) AS ls_awc_not_open_holiday, ' ||
    'sum(awc_not_open_unknown) AS ls_awc_not_open_unknown, ' ||
    'sum(awc_not_open_other) AS ls_awc_not_open_other '
    'FROM ' || quote_ident(_ls_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' GROUP BY awc_id, month) ut ' ||
  'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';


  -- Get latest infrastructure data
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'infra_last_update_date = ut.infra_last_update_date, ' ||
    'infra_type_of_building = ut.infra_type_of_building, ' ||
    'infra_type_of_building_pucca = ut.infra_type_of_building_pucca, ' ||
    'infra_type_of_building_semi_pucca = ut.infra_type_of_building_semi_pucca, ' ||
    'infra_type_of_building_kuccha = ut.infra_type_of_building_kuccha, ' ||
    'infra_type_of_building_partial_covered_space = ut.infra_type_of_building_partial_covered_space, ' ||
    'infra_clean_water = ut.infra_clean_water, ' ||
    'infra_functional_toilet = ut.infra_functional_toilet, ' ||
    'infra_baby_weighing_scale = ut.infra_baby_weighing_scale, ' ||
    'infra_flat_weighing_scale = ut.infra_flat_weighing_scale, ' ||
    'infra_adult_weighing_scale = ut.infra_adult_weighing_scale, ' ||
    'infra_infant_weighing_scale = ut.infra_infant_weighing_scale, ' ||
    'infra_cooking_utensils = ut.infra_cooking_utensils, ' ||
    'infra_medicine_kits = ut.infra_medicine_kits, ' ||
    'infra_adequate_space_pse = ut.infra_adequate_space_pse, ' ||
    'electricity_awc = ut.electricity_awc, ' ||
    'infantometer = ut.infantometer, ' ||
    'stadiometer = ut.stadiometer ' ||
  'FROM (SELECT DISTINCT ON (awc_id) ' ||
    'awc_id, ' ||
    'month, ' ||
    'submitted_on AS infra_last_update_date, ' ||
    'type_of_building AS infra_type_of_building, ' ||
    'type_of_building_pucca AS infra_type_of_building_pucca, ' ||
    'type_of_building_semi_pucca AS infra_type_of_building_semi_pucca, ' ||
    'type_of_building_kuccha AS infra_type_of_building_kuccha, ' ||
    'type_of_building_partial_covered_space AS infra_type_of_building_partial_covered_space, ' ||
    'clean_water AS infra_clean_water, ' ||
    'functional_toilet AS infra_functional_toilet, ' ||
    'baby_scale_usable AS infra_baby_weighing_scale, ' ||
    'flat_scale_usable AS infra_flat_weighing_scale, ' ||
    'GREATEST(adult_scale_available, adult_scale_usable) AS infra_adult_weighing_scale, ' ||
    'GREATEST(baby_scale_available, flat_scale_available, baby_scale_usable) AS infra_infant_weighing_scale, ' ||
    'cooking_utensils_usable AS infra_cooking_utensils, ' ||
    'medicine_kits_usable AS infra_medicine_kits, ' ||
    'has_adequate_space_pse AS infra_adequate_space_pse, ' ||
    'electricity_awc AS electricity_awc, ' ||
    'infantometer AS infantometer, ' ||
    'stadiometer AS stadiometer ' ||
    'FROM ' || quote_ident(_infra_tablename) || ' ' ||
    'WHERE month <= ' || quote_literal(_end_date) || ' ORDER BY awc_id, submitted_on DESC) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';
    -- could possibly add multicol indexes to make order by faster?

  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'num_awc_infra_last_update = 1 WHERE infra_last_update_date IS NOT NULL';

  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'num_awc_infra_last_update = 0 WHERE infra_last_update_date IS NULL';

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
    'avg(usage_time_pse), ' ||
    'avg(usage_time_gmp), ' ||
    'avg(usage_time_bp), ' ||
    'avg(usage_time_pnc), ' ||
    'avg(usage_time_ebf), ' ||
    'avg(usage_time_cf), ' ||
    'avg(usage_time_of_day_pse), ' ||
    'avg(usage_time_of_day_home_visit), ' ||
    'sum(vhnd_immunization), ' ||
    'sum(vhnd_anc), ' ||
    'sum(vhnd_gmp), ' ||
    'sum(vhnd_num_pregnancy), ' ||
    'sum(vhnd_num_lactating), ' ||
    'sum(vhnd_num_mothers_6_12), ' ||
    'sum(vhnd_num_mothers_12), ' ||
    'sum(vhnd_num_fathers), ' ||
    'sum(ls_supervision_visit), ' ||
    'sum(ls_num_supervised), ' ||
    'avg(ls_awc_location_long), ' ||
    'avg(ls_awc_location_lat), ' ||
    'sum(ls_awc_present), ' ||
    'sum(ls_awc_open), ' ||
    'sum(ls_awc_not_open_aww_not_available), ' ||
    'sum(ls_awc_not_open_closed_early), ' ||
    'sum(ls_awc_not_open_holiday), ' ||
    'sum(ls_awc_not_open_unknown), ' ||
    'sum(ls_awc_not_open_other), ' ||
    quote_nullable(_null_value) || ', ' ||
    quote_nullable(_null_value) || ', ' ||
    'sum(infra_type_of_building_pucca), ' ||
    'sum(infra_type_of_building_semi_pucca), ' ||
    'sum(infra_type_of_building_kuccha), ' ||
    'sum(infra_type_of_building_partial_covered_space), ' ||
    'sum(infra_clean_water), ' ||
    'sum(infra_functional_toilet), ' ||
    'sum(infra_baby_weighing_scale), ' ||
    'sum(infra_flat_weighing_scale), ' ||
    'sum(infra_adult_weighing_scale), ' ||
    'sum(infra_cooking_utensils), ' ||
    'sum(infra_medicine_kits), ' ||
    'sum(infra_adequate_space_pse), ' ||
    'sum(usage_num_hh_reg), ' ||
    'sum(usage_num_add_person), ' ||
    'sum(usage_num_add_pregnancy), ' ||
    quote_literal(_yes_text) || ', ' ||
    quote_nullable(_null_value) || ', ' ||
    'sum(trained_phase_1), ' ||
    'sum(trained_phase_2), ' ||
    'sum(trained_phase_3), ' ||
    'sum(trained_phase_4), ';

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
    'usage_time_pse, ' ||
    'usage_time_gmp, ' ||
    'usage_time_bp, ' ||
    'usage_time_pnc, ' ||
    'usage_time_ebf, ' ||
    'usage_time_cf, ' ||
    'usage_time_of_day_pse, ' ||
    'usage_time_of_day_home_visit, ' ||
    'vhnd_immunization, ' ||
    'vhnd_anc, ' ||
    'vhnd_gmp, ' ||
    'vhnd_num_pregnancy, ' ||
    'vhnd_num_lactating, ' ||
    'vhnd_num_mothers_6_12, ' ||
    'vhnd_num_mothers_12, ' ||
    'vhnd_num_fathers, ' ||
    'ls_supervision_visit, ' ||
    'ls_num_supervised, ' ||
    'ls_awc_location_long, ' ||
    'ls_awc_location_lat, ' ||
    'ls_awc_present, ' ||
    'ls_awc_open, ' ||
    'ls_awc_not_open_aww_not_available, ' ||
    'ls_awc_not_open_closed_early, ' ||
    'ls_awc_not_open_holiday, ' ||
    'ls_awc_not_open_unknown, ' ||
    'ls_awc_not_open_other, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_type_of_building_pucca, ' ||
    'infra_type_of_building_semi_pucca, ' ||
    'infra_type_of_building_kuccha, ' ||
    'infra_type_of_building_partial_covered_space, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_flat_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'training_phase, ' ||
    'trained_phase_1, ' ||
    'trained_phase_2, ' ||
    'trained_phase_3, ' ||
    'trained_phase_4, ' ||
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
    'usage_time_pse, ' ||
    'usage_time_gmp, ' ||
    'usage_time_bp, ' ||
    'usage_time_pnc, ' ||
    'usage_time_ebf, ' ||
    'usage_time_cf, ' ||
    'usage_time_of_day_pse, ' ||
    'usage_time_of_day_home_visit, ' ||
    'vhnd_immunization, ' ||
    'vhnd_anc, ' ||
    'vhnd_gmp, ' ||
    'vhnd_num_pregnancy, ' ||
    'vhnd_num_lactating, ' ||
    'vhnd_num_mothers_6_12, ' ||
    'vhnd_num_mothers_12, ' ||
    'vhnd_num_fathers, ' ||
    'ls_supervision_visit, ' ||
    'ls_num_supervised, ' ||
    'ls_awc_location_long, ' ||
    'ls_awc_location_lat, ' ||
    'ls_awc_present, ' ||
    'ls_awc_open, ' ||
    'ls_awc_not_open_aww_not_available, ' ||
    'ls_awc_not_open_closed_early, ' ||
    'ls_awc_not_open_holiday, ' ||
    'ls_awc_not_open_unknown, ' ||
    'ls_awc_not_open_other, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_type_of_building_pucca, ' ||
    'infra_type_of_building_semi_pucca, ' ||
    'infra_type_of_building_kuccha, ' ||
    'infra_type_of_building_partial_covered_space, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_flat_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'training_phase, ' ||
    'trained_phase_1, ' ||
    'trained_phase_2, ' ||
    'trained_phase_3, ' ||
    'trained_phase_4, ' ||
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
    'usage_time_pse, ' ||
    'usage_time_gmp, ' ||
    'usage_time_bp, ' ||
    'usage_time_pnc, ' ||
    'usage_time_ebf, ' ||
    'usage_time_cf, ' ||
    'usage_time_of_day_pse, ' ||
    'usage_time_of_day_home_visit, ' ||
    'vhnd_immunization, ' ||
    'vhnd_anc, ' ||
    'vhnd_gmp, ' ||
    'vhnd_num_pregnancy, ' ||
    'vhnd_num_lactating, ' ||
    'vhnd_num_mothers_6_12, ' ||
    'vhnd_num_mothers_12, ' ||
    'vhnd_num_fathers, ' ||
    'ls_supervision_visit, ' ||
    'ls_num_supervised, ' ||
    'ls_awc_location_long, ' ||
    'ls_awc_location_lat, ' ||
    'ls_awc_present, ' ||
    'ls_awc_open, ' ||
    'ls_awc_not_open_aww_not_available, ' ||
    'ls_awc_not_open_closed_early, ' ||
    'ls_awc_not_open_holiday, ' ||
    'ls_awc_not_open_unknown, ' ||
    'ls_awc_not_open_other, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_type_of_building_pucca, ' ||
    'infra_type_of_building_semi_pucca, ' ||
    'infra_type_of_building_kuccha, ' ||
    'infra_type_of_building_partial_covered_space, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_flat_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'training_phase, ' ||
    'trained_phase_1, ' ||
    'trained_phase_2, ' ||
    'trained_phase_3, ' ||
    'trained_phase_4, ' ||
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
    'usage_time_pse, ' ||
    'usage_time_gmp, ' ||
    'usage_time_bp, ' ||
    'usage_time_pnc, ' ||
    'usage_time_ebf, ' ||
    'usage_time_cf, ' ||
    'usage_time_of_day_pse, ' ||
    'usage_time_of_day_home_visit, ' ||
    'vhnd_immunization, ' ||
    'vhnd_anc, ' ||
    'vhnd_gmp, ' ||
    'vhnd_num_pregnancy, ' ||
    'vhnd_num_lactating, ' ||
    'vhnd_num_mothers_6_12, ' ||
    'vhnd_num_mothers_12, ' ||
    'vhnd_num_fathers, ' ||
    'ls_supervision_visit, ' ||
    'ls_num_supervised, ' ||
    'ls_awc_location_long, ' ||
    'ls_awc_location_lat, ' ||
    'ls_awc_present, ' ||
    'ls_awc_open, ' ||
    'ls_awc_not_open_aww_not_available, ' ||
    'ls_awc_not_open_closed_early, ' ||
    'ls_awc_not_open_holiday, ' ||
    'ls_awc_not_open_unknown, ' ||
    'ls_awc_not_open_other, ' ||
    'infra_last_update_date, ' ||
    'infra_type_of_building, ' ||
    'infra_type_of_building_pucca, ' ||
    'infra_type_of_building_semi_pucca, ' ||
    'infra_type_of_building_kuccha, ' ||
    'infra_type_of_building_partial_covered_space, ' ||
    'infra_clean_water, ' ||
    'infra_functional_toilet, ' ||
    'infra_baby_weighing_scale, ' ||
    'infra_flat_weighing_scale, ' ||
    'infra_adult_weighing_scale, ' ||
    'infra_cooking_utensils, ' ||
    'infra_medicine_kits, ' ||
    'infra_adequate_space_pse, ' ||
    'usage_num_hh_reg, ' ||
    'usage_num_add_person, ' ||
    'usage_num_add_pregnancy, ' ||
    'is_launched, ' ||
    'training_phase, ' ||
    'trained_phase_1, ' ||
    'trained_phase_2, ' ||
    'trained_phase_3, ' ||
    'trained_phase_4, ' ||
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
