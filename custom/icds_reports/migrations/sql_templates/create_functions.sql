-- Table Types Referenced
-- 	awc_location
-- 	child_health_monthly
--	ccs_record_monthly
--	daily_feeding
--	usage
--	vhnd
--	awc_mgmt
--	infrastructure

-- Update months table
CREATE OR REPLACE FUNCTION update_months_table(date) RETURNS void AS
$BODY$
BEGIN
    INSERT INTO "icds_months" (month_name, start_date, end_date)
	SELECT
		to_char($1, 'Mon YYYY'),
		date_trunc('MONTH', $1)::DATE,
		(date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 day')::DATE
	WHERE NOT EXISTS (SELECT 1 FROM "icds_months" WHERE start_date=date_trunc('MONTH', $1)::DATE);
END;
$BODY$
LANGUAGE plpgsql;

-- Update Locations Table
CREATE OR REPLACE FUNCTION update_location_table() RETURNS VOID AS
$BODY$
DECLARE
	_ucr_location_table text;
BEGIN
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('awc_location') INTO _ucr_location_table;

	EXECUTE 'DELETE FROM awc_location';
	EXECUTE 'INSERT INTO awc_location (SELECT ' ||
		'doc_id, ' ||
		'awc_name, ' ||
		'awc_site_code, ' ||
		'supervisor_id, ' ||
		'supervisor_name, ' ||
		'supervisor_site_code, ' ||
		'block_id, ' ||
		'block_name, ' ||
		'block_site_code, ' ||
		'district_id, ' ||
		'district_name, ' ||
		'district_site_code, ' ||
		'state_id, ' ||
		'state_name, ' ||
		'state_site_code, ' ||
		'5, ' ||
		'block_map_location_name, ' ||
		'district_map_location_name, ' ||
		'state_map_location_name FROM ' || quote_ident(_ucr_location_table) || ')';
END;
$BODY$
LANGUAGE plpgsql;

-- Create new month tables
CREATE OR REPLACE FUNCTION create_new_table_for_month(text, date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
BEGIN
	_tablename := $1 || '_' || (date_trunc('MONTH', $2)::DATE);
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename);
	EXECUTE 'CREATE TABLE ' || quote_ident(_tablename) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' )' ||
	    ') INHERITS ('  || quote_ident($1) || ')';
END;
$BODY$
LANGUAGE plpgsql;

-- Create new aggregate month tables
CREATE OR REPLACE FUNCTION create_new_aggregate_table_for_month(text, date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
	_tablename1 text;
	_tablename2 text;
	_tablename3 text;
	_tablename4 text;
	_tablename5 text;
BEGIN
	-- This is for cleaning up old style non-aggregation level partioned tables
	_tablename := $1 || '_' || (date_trunc('MONTH', $2)::DATE);
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename);

	_tablename1 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_1';
	_tablename2 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_2';
	_tablename3 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_3';
	_tablename4 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_4';
	_tablename5 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_5';
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename1);
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename2);
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename3);
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename4);
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename5);

	EXECUTE 'CREATE TABLE ' || quote_ident(_tablename1) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 1)' ||
	    ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename2) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 2)' ||
	    ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename3) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 3)' ||
	    ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename4) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 4)' ||
	    ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename5) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 5)' ||
	    ') INHERITS ('  || quote_ident($1) || ')';
END;
$BODY$
LANGUAGE plpgsql;

-- Copy into child_health_monthly
CREATE OR REPLACE FUNCTION insert_into_child_health_monthly(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
	_ucr_child_monthly_table text;
	_start_date date;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename := 'child_health_monthly' || '_' || _start_date;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('child_health_monthly') INTO _ucr_child_monthly_table;

	EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
	'(SELECT ' ||
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
		'cf_in_month, ' ||
		'cf_diet_diversity, ' ||
		'cf_diet_quantity, ' ||
		'cf_handwashing, ' ||
		'cf_demo, ' ||
		'fully_immunized_eligible, ' ||
		'fully_immunized_on_time, ' ||
		'fully_immunized_late, ' ||
		'counsel_ebf, ' ||
		'counsel_adequate_bf, ' ||
		'counsel_pediatric_ifa, ' ||
		'counsel_comp_feeding_vid, ' ||
		'counsel_increase_food_bf, ' ||
		'counsel_manage_breast_problems, ' ||
		'counsel_skin_to_skin, ' ||
		'counsel_immediate_breastfeeding, ' ||
		'weight_recorded_in_month, ' ||
		'height_recorded_in_month, ' ||
		'has_aadhar_id, ' ||
		'thr_eligible, ' ||
		'pnc_eligible, ' ||
		'cf_initiated, ' ||
		'cf_initiation_eligible, ' ||
		'height_measured_in_month, ' ||
		'current_month_stunting, ' ||
		'stunting_last_recorded, ' ||
		'wasting_last_recorded, ' ||
		'current_month_wasting, ' ||
		'valid_in_month, ' ||
		'valid_all_registered_in_month, ' ||
		'ebf_no_info_recorded, ' ||
		'dob ' ||
		'FROM ' || quote_ident(_ucr_child_monthly_table) || ' WHERE month = ' || quote_literal(_start_date) || ')';

    EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id, case_id)';

    -- There may be better indexes to put here. Should investigate what tableau queries
END;
$BODY$
LANGUAGE plpgsql;


-- Copy into ccs_record_monthly
CREATE OR REPLACE FUNCTION insert_into_ccs_record_monthly(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
	_ucr_ccs_record_table text;
	_start_date date;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename := 'ccs_record_monthly' || '_' || _start_date;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('ccs_record_monthly') INTO _ucr_ccs_record_table;

	EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'awc_id, ' ||
		'case_id, ' ||
		'month, ' ||
		'age_in_months, ' ||
		'ccs_status, ' ||
		'open_in_month, ' ||
		'alive_in_month, ' ||
		'trimester, ' ||
		'num_rations_distributed, ' ||
		'thr_eligible, ' ||
		'tetanus_complete, ' ||
		'delivered_in_month, ' ||
		'anc1_received_at_delivery, ' ||
		'anc2_received_at_delivery, ' ||
		'anc3_received_at_delivery, ' ||
		'anc4_received_at_delivery, ' ||
		'registration_trimester_at_delivery, ' ||
		'using_ifa, ' ||
		'ifa_consumed_last_seven_days, ' ||
		'anemic_severe, ' ||
		'anemic_moderate, ' ||
		'anemic_normal, ' ||
		'anemic_unknown, ' ||
		'extra_meal, ' ||
		'resting_during_pregnancy, ' ||
		'bp_visited_in_month, ' ||
		'pnc_visited_in_month, ' ||
		'trimester_2, ' ||
		'trimester_3, ' ||
		'counsel_immediate_bf, ' ||
		'counsel_bp_vid, ' ||
		'counsel_preparation, ' ||
		'counsel_bp_vid, ' ||
		'counsel_immediate_conception, ' ||
		'counsel_accessible_postpartum_fp, ' ||
		'bp1_complete, ' ||
		'bp2_complete, ' ||
		'bp3_complete, ' ||
		'pnc_complete, ' ||
		'postnatal, ' ||
		'has_aadhar_id, ' ||
		'counsel_fp_methods, ' ||
		'pregnant, ' ||
		'pregnant_all, ' ||
		'lactating, ' ||
		'lactating_all, ' ||
		'institutional_delivery_in_month, ' ||
		'add ' ||
		'FROM ' || quote_ident(_ucr_ccs_record_table) || ' WHERE month = ' || quote_literal(_start_date) || ')';

		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id, case_id)';
        -- There may be better indexes to put here. Should investigate what tableau queries
END;
$BODY$
LANGUAGE plpgsql;

-- Copy into daily_attendance
CREATE OR REPLACE FUNCTION insert_into_daily_attendance(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
	_daily_attendance_tablename text;
	_start_date date;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename := 'daily_attendance' || '_' || _start_date;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('daily_feeding') INTO _daily_attendance_tablename;

	EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'doc_id, ' ||
		'awc_id, ' ||
		'month, ' ||
		'submitted_on AS pse_date, ' ||
		'awc_open_count, ' ||
		'1, ' ||
		'eligible_children, ' ||
		'attended_children, ' ||
		'attended_children_percent, ' ||
		'form_location, ' ||
		'form_location_lat, ' ||
		'form_location_long, ' ||
		'image_name ' ||
		'FROM ' || quote_ident(_daily_attendance_tablename) || ' WHERE month = ' || quote_literal(_start_date) || ')';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id)';
        -- There may be better indexes to put here. Should investigate what tableau queries
END;
$BODY$
LANGUAGE plpgsql;

-- Aggregate into agg_child_health
CREATE OR REPLACE FUNCTION aggregate_child_health(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename1 text;
	_tablename2 text;
	_tablename3 text;
	_tablename4 text;
	_tablename5 text;
	_ucr_child_monthly_table text;
	_start_date date;
	_end_date date;
	_all_text text;
	_null_value text;
	_blank_value text;
	_no_text text;
	_rollup_text text;
	_rollup_text2 text;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename1 := 'agg_child_health' || '_' || _start_date || '_1';
	_tablename2 := 'agg_child_health' || '_' || _start_date || '_2';
	_tablename3 := 'agg_child_health' || '_' || _start_date || '_3';
	_tablename4 := 'agg_child_health' || '_' || _start_date || '_4';
	_tablename5 := 'agg_child_health' || '_' || _start_date || '_5';
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('child_health_monthly') INTO _ucr_child_monthly_table;
	_all_text = 'All';
	_null_value = NULL;
	_blank_value = '';
	_no_text = 'no';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename5) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id, ' ||
		'month, ' ||
		'sex, ' ||
		'age_tranche, ' ||
		'caste, ' ||
		'COALESCE(disabled, ' || quote_nullable(_no_text) || '), ' ||
		'COALESCE(minority, ' || quote_nullable(_no_text) || '), ' ||
		'COALESCE(resident, ' || quote_nullable(_no_text) || '), ' ||
		'sum(valid_in_month), ' ||
		'sum(nutrition_status_weighed), ' ||
		'sum(nutrition_status_unweighed), ' ||
		'sum(CASE WHEN nutrition_status_normal = 1 AND nutrition_status_weighed = 1 THEN 1 ELSE 0 END), ' ||
		'sum(CASE WHEN nutrition_status_moderately_underweight = 1 AND nutrition_status_weighed = 1 THEN 1 ELSE 0 END), ' ||
		'sum(CASE WHEN nutrition_status_severely_underweight = 1 AND nutrition_status_weighed = 1 THEN 1 ELSE 0 END), ' ||
		'sum(wer_eligible), ' ||
		'sum(thr_eligible), ' ||
		'sum(rations_21_plus_distributed), ' ||
		'sum(pse_eligible), ' ||
		'sum(pse_attended_16_days), ' ||
		'sum(born_in_month), ' ||
		'sum(low_birth_weight_born_in_month), ' ||
		'sum(bf_at_birth_born_in_month), ' ||
		'sum(ebf_eligible), ' ||
		'sum(ebf_in_month), ' ||
		'sum(cf_eligible), ' ||
		'sum(cf_in_month), ' ||
		'sum(cf_diet_diversity), ' ||
		'sum(cf_diet_quantity), ' ||
		'sum(cf_demo), ' ||
		'sum(cf_handwashing), ' ||
		'sum(counsel_increase_food_bf), ' ||
		'sum(counsel_manage_breast_problems), ' ||
		'sum(counsel_ebf), ' ||
		'sum(counsel_adequate_bf), ' ||
		'sum(counsel_pediatric_ifa), ' ||
		'sum(counsel_comp_feeding_vid), ' ||
		'sum(fully_immunized_eligible), ' ||
		'sum(fully_immunized_on_time), ' ||
		'sum(fully_immunized_late), ' ||
		'sum(has_aadhar_id), ' ||
		'5, ' ||
		'sum(pnc_eligible), ' ||
		'sum(height_eligible), ' ||
		'sum(CASE WHEN wasting_moderate = 1 AND nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
		'sum(CASE WHEN wasting_severe = 1 AND nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
		'sum(CASE WHEN stunting_moderate = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
		'sum(CASE WHEN stunting_severe = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
		'sum(cf_initiated), ' ||
		'sum(cf_initiation_eligible), ' ||
		'sum(height_measured_in_month), ' ||
		'sum(CASE WHEN wasting_normal = 1 AND nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
		'sum(CASE WHEN stunting_normal = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
		'sum(valid_all_registered_in_month), ' ||
		'sum(ebf_no_info_recorded), ' ||
		'sum(CASE WHEN nutrition_status_weighed = 1 AND height_measured_in_month = 1 THEN 1 ELSE 0 END), ' ||
		'sum(CASE WHEN (born_in_month = 1 AND (nutrition_status_weighed = 1 OR low_birth_weight_born_in_month = 1)) THEN 1 ELSE 0 END) ' ||
		'FROM ' || quote_ident(_ucr_child_monthly_table) || ' ' ||
    'WHERE state_id != ' || quote_literal(_blank_value) ||  ' AND month = ' || quote_literal(_start_date) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, sex, age_tranche, caste, disabled, minority, resident)';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx1') || ' ON ' || quote_ident(_tablename5) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx5') || ' ON ' || quote_ident(_tablename5) || '(awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx6') || ' ON ' || quote_ident(_tablename5) || '(gender)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx7') || ' ON ' || quote_ident(_tablename5) || '(age_tranche)';


	--Roll up by location
	_rollup_text = 'sum(valid_in_month), ' ||
		'sum(nutrition_status_weighed), ' ||
		'sum(nutrition_status_unweighed), ' ||
		'sum(nutrition_status_normal), ' ||
		'sum(nutrition_status_moderately_underweight), ' ||
		'sum(nutrition_status_severely_underweight), ' ||
		'sum(wer_eligible), ' ||
		'sum(thr_eligible), ' ||
		'sum(rations_21_plus_distributed), ' ||
		'sum(pse_eligible), ' ||
		'sum(pse_attended_16_days), ' ||
		'sum(born_in_month), ' ||
		'sum(low_birth_weight_in_month), ' ||
		'sum(bf_at_birth), ' ||
		'sum(ebf_eligible), ' ||
		'sum(ebf_in_month), ' ||
		'sum(cf_eligible), ' ||
		'sum(cf_in_month), ' ||
		'sum(cf_diet_diversity), ' ||
		'sum(cf_diet_quantity), ' ||
		'sum(cf_demo), ' ||
		'sum(cf_handwashing), ' ||
		'sum(counsel_increase_food_bf), ' ||
		'sum(counsel_manage_breast_problems), ' ||
		'sum(counsel_ebf), ' ||
		'sum(counsel_adequate_bf), ' ||
		'sum(counsel_pediatric_ifa), ' ||
		'sum(counsel_play_cf_video), ' ||
		'sum(fully_immunized_eligible), ' ||
		'sum(fully_immunized_on_time), ' ||
		'sum(fully_immunized_late), ' ||
		'sum(has_aadhar_id), ';

	_rollup_text2 = 'sum(pnc_eligible), ' ||
		'sum(height_eligible), ' ||
	    'sum(wasting_moderate), ' ||
	    'sum(wasting_severe), ' ||
	    'sum(stunting_moderate), ' ||
	    'sum(stunting_severe), ' ||
	    'sum(cf_initiation_in_month), ' ||
	    'sum(cf_initiation_eligible), ' ||
	    'sum(height_measured_in_month), ' ||
	    'sum(wasting_normal), ' ||
	    'sum(stunting_normal), ' ||
	    'sum(valid_all_registered_in_month), ' ||
	    'sum(ebf_no_info_recorded), ' ||
      'sum(weighed_and_height_measured_in_month), ' ||
      'sum(weighed_and_born_in_month) ';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'4, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename5) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, month, gender, age_tranche)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx1') || ' ON ' || quote_ident(_tablename4) || '(state_id, district_id, block_id, supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx5') || ' ON ' || quote_ident(_tablename4) || '(gender)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx6') || ' ON ' || quote_ident(_tablename4) || '(age_tranche)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'3, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename4) || ' ' ||
		'GROUP BY state_id, district_id, block_id, month, gender, age_tranche)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx1') || ' ON ' || quote_ident(_tablename3) || '(state_id, district_id, block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx4') || ' ON ' || quote_ident(_tablename3) || '(gender)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx5') || ' ON ' || quote_ident(_tablename3) || '(age_tranche)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'2, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename3) || ' ' ||
		'GROUP BY state_id, district_id, month, gender, age_tranche)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx1') || ' ON ' || quote_ident(_tablename2) || '(state_id, district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx3') || ' ON ' || quote_ident(_tablename2) || '(gender)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx4') || ' ON ' || quote_ident(_tablename2) || '(age_tranche)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || '(SELECT ' ||
		'state_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'1, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename2) || ' ' ||
		'GROUP BY state_id, month, gender, age_tranche)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx1') || ' ON ' || quote_ident(_tablename1) || '(state_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx2') || ' ON ' || quote_ident(_tablename1) || '(gender)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx3') || ' ON ' || quote_ident(_tablename1) || '(age_tranche)';
END;
$BODY$
LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION aggregate_ccs_record(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename1 text;
	_tablename2 text;
	_tablename3 text;
	_tablename4 text;
	_tablename5 text;
	_ucr_ccs_record_table text;
	_start_date date;
	_end_date date;
	_all_text text;
	_null_value text;
	_blank_value text;
	_no_text text;
	_rollup_text text;
	_rollup_text2 text;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename1 := 'agg_ccs_record' || '_' || _start_date || '_1';
	_tablename2 := 'agg_ccs_record' || '_' || _start_date || '_2';
	_tablename3 := 'agg_ccs_record' || '_' || _start_date || '_3';
	_tablename4 := 'agg_ccs_record' || '_' || _start_date || '_4';
	_tablename5 := 'agg_ccs_record' || '_' || _start_date || '_5';
	_all_text = 'All';
	_null_value = NULL;
	_blank_value = '';
	_no_text = 'no';
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('ccs_record_monthly') INTO _ucr_ccs_record_table;

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename5) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id, ' ||
		'month, ' ||
		'ccs_status, ' ||
		'COALESCE(trimester::text, ' || quote_nullable(_blank_value) || '), ' ||
		'caste, ' ||
		'COALESCE(disabled, ' || quote_nullable(_no_text) || '), ' ||
		'COALESCE(minority, ' || quote_nullable(_no_text) || '), ' ||
		'COALESCE(resident, ' || quote_nullable(_no_text) || '), ' ||
		'sum(valid_in_month), ' ||
		'sum(lactating), ' ||
		'sum(pregnant), ' ||
		'sum(thr_eligible), ' ||
		'sum(rations_21_plus_distributed), ' ||
		'sum(tetanus_complete), ' ||
		'sum(delivered_in_month), ' ||
		'sum(anc1_received_at_delivery), ' ||
		'sum(anc2_received_at_delivery), ' ||
		'sum(anc3_received_at_delivery), ' ||
		'sum(anc4_received_at_delivery), ' ||
		'avg(registration_trimester_at_delivery), ' ||
		'sum(using_ifa), ' ||
		'sum(ifa_consumed_last_seven_days), ' ||
		'sum(anemic_normal), ' ||
		'sum(anemic_moderate), ' ||
		'sum(anemic_severe), ' ||
		'sum(anemic_unknown), ' ||
		'sum(extra_meal), ' ||
		'sum(resting_during_pregnancy), ' ||
		'sum(bp1_complete), ' ||
		'sum(bp2_complete), ' ||
		'sum(bp3_complete), ' ||
		'sum(pnc_complete), ' ||
		'sum(trimester_2), ' ||
		'sum(trimester_3), ' ||
		'sum(postnatal), ' ||
		'sum(counsel_bp_vid), ' ||
		'sum(counsel_preparation), ' ||
		'sum(counsel_immediate_bf), ' ||
		'sum(counsel_fp_vid), ' ||
		'sum(counsel_immediate_conception), ' ||
		'sum(counsel_accessible_postpartum_fp), ' ||
		'sum(has_aadhar_id), ' ||
		'5, '
		'sum(valid_all_registered_in_month), ' ||
		'sum(institutional_delivery_in_month), ' ||
		'sum(lactating_all), ' ||
		'sum(pregnant_all) ' ||
		'FROM ' || quote_ident(_ucr_ccs_record_table) || ' ' ||
    'WHERE state_id != ' || quote_literal(_blank_value) ||  ' AND month = ' || quote_literal(_start_date) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, ccs_status, trimester, caste, disabled, minority, resident)';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx1') || ' ON ' || quote_ident(_tablename5) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx5') || ' ON ' || quote_ident(_tablename5) || '(awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx6') || ' ON ' || quote_ident(_tablename5) || '(ccs_status)';

    -- may want a double index on month and caste for aggregate  location query

	--Roll up by location
	_rollup_text = 'sum(valid_in_month), ' ||
		'sum(lactating), ' ||
		'sum(pregnant), ' ||
		'sum(thr_eligible), ' ||
		'sum(rations_21_plus_distributed), ' ||
		'sum(tetanus_complete), ' ||
		'sum(delivered_in_month), ' ||
		'sum(anc1_received_at_delivery), ' ||
		'sum(anc2_received_at_delivery), ' ||
		'sum(anc3_received_at_delivery), ' ||
		'sum(anc4_received_at_delivery), ' ||
		'avg(registration_trimester_at_delivery), ' ||
		'sum(using_ifa), ' ||
		'sum(ifa_consumed_last_seven_days), ' ||
		'sum(anemic_normal), ' ||
		'sum(anemic_moderate), ' ||
		'sum(anemic_severe), ' ||
		'sum(anemic_unknown), ' ||
		'sum(extra_meal), ' ||
		'sum(resting_during_pregnancy), ' ||
		'sum(bp1_complete), ' ||
		'sum(bp2_complete), ' ||
		'sum(bp3_complete), ' ||
		'sum(pnc_complete), ' ||
		'sum(trimester_2), ' ||
		'sum(trimester_3), ' ||
		'sum(postnatal), ' ||
		'sum(counsel_bp_vid), ' ||
		'sum(counsel_preparation), ' ||
		'sum(counsel_immediate_bf), ' ||
		'sum(counsel_fp_vid), ' ||
		'sum(counsel_immediate_conception), ' ||
		'sum(counsel_accessible_postpartum_fp), ' ||
		'sum(has_aadhar_id), ';

	_rollup_text2 = 'sum(valid_all_registered_in_month), ' ||
		'sum(institutional_delivery_in_month), ' ||
		'sum(lactating_all), ' ||
		'sum(pregnant_all) ';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'4, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename5) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, month, ccs_status)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx1') || ' ON ' || quote_ident(_tablename4) || '(state_id, district_id, block_id, supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx2') || ' ON ' || quote_ident(_tablename4) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx3') || ' ON ' || quote_ident(_tablename4) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx4') || ' ON ' || quote_ident(_tablename4) || '(supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx5') || ' ON ' || quote_ident(_tablename4) || '(ccs_status)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'3, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename4) || ' ' ||
		'GROUP BY state_id, district_id, block_id, month, ccs_status)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx1') || ' ON ' || quote_ident(_tablename3) || '(state_id, district_id, block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx2') || ' ON ' || quote_ident(_tablename3) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx3') || ' ON ' || quote_ident(_tablename3) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx4') || ' ON ' || quote_ident(_tablename3) || '(ccs_status)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'2, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename3) || ' ' ||
		'GROUP BY state_id, district_id, month, ccs_status)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx1') || ' ON ' || quote_ident(_tablename2) || '(state_id, district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx2') || ' ON ' || quote_ident(_tablename2) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx3') || ' ON ' || quote_ident(_tablename2) || '(ccs_status)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || '(SELECT ' ||
		'state_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		_rollup_text ||
		'1, ' ||
		_rollup_text2 ||
		'FROM ' || quote_ident(_tablename2) || ' ' ||
		'GROUP BY state_id, month, ccs_status)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx1') || ' ON ' || quote_ident(_tablename1) || '(state_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx2') || ' ON ' || quote_ident(_tablename1) || '(ccs_status)';
END;
$BODY$
LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION aggregate_thr_data(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename1 text;
	_tablename2 text;
	_tablename3 text;
	_tablename4 text;
	_tablename5 text;
	_child_health_tablename text;
	_ccs_record_tablename text;
	_start_date date;
	_all_text text;
	_null_value text;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename1 := 'agg_thr_data' || '_' || _start_date || '_1';
	_tablename2 := 'agg_thr_data' || '_' || _start_date || '_2';
	_tablename3 := 'agg_thr_data' || '_' || _start_date || '_3';
	_tablename4 := 'agg_thr_data' || '_' || _start_date || '_4';
	_tablename5 := 'agg_thr_data' || '_' || _start_date || '_5';
	_child_health_tablename := 'agg_child_health';
	_ccs_record_tablename := 'agg_ccs_record';
	_all_text = 'All';
	_null_value = NULL;

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename5) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id, ' ||
		'month, ' ||
		quote_literal('child') || ',' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
		'sum(thr_eligible), ' ||
		'sum(rations_21_plus_distributed), ' ||
		'aggregation_level ' ||
		'FROM ' || quote_ident(_child_health_tablename) || ' ' ||
		'WHERE (aggregation_level = 5 AND month = ' || quote_literal(_start_date) || ') '
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, caste, disabled, minority, resident, aggregation_level)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename5) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id, ' ||
		'month, ' ||
		'ccs_status,' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
		'sum(thr_eligible),' ||
		'sum(rations_21_plus_distributed), ' ||
		'aggregation_level ' ||
		'FROM ' || quote_ident(_ccs_record_tablename) || ' ' ||
		'WHERE (aggregation_level = 5 AND month = ' || quote_literal(_start_date) || ') '
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, ccs_status, caste, disabled, minority, resident, aggregation_level)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx1') || ' ON ' || quote_ident(_tablename5) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx2') || ' ON ' || quote_ident(_tablename5) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx3') || ' ON ' || quote_ident(_tablename5) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx4') || ' ON ' || quote_ident(_tablename5) || '(supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx5') || ' ON ' || quote_ident(_tablename5) || '(awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename5 || '_indx6') || ' ON ' || quote_ident(_tablename5) || '(beneficiary_type)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'beneficiary_type, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'sum(thr_eligible),' ||
		'sum(rations_21_plus_distributed), ' ||
		'4 ' ||
		'FROM ' || quote_ident(_tablename5) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, month, beneficiary_type)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx1') || ' ON ' || quote_ident(_tablename4) || '(state_id, district_id, block_id, supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx2') || ' ON ' || quote_ident(_tablename4) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx3') || ' ON ' || quote_ident(_tablename4) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx4') || ' ON ' || quote_ident(_tablename4) || '(supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename4 || '_indx5') || ' ON ' || quote_ident(_tablename4) || '(beneficiary_type)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'beneficiary_type, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'sum(thr_eligible),' ||
		'sum(rations_21_plus_distributed), ' ||
		'3 ' ||
		'FROM ' || quote_ident(_tablename4) || ' ' ||
		'GROUP BY state_id, district_id, block_id, month, beneficiary_type)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx1') || ' ON ' || quote_ident(_tablename3) || '(state_id, district_id, block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx2') || ' ON ' || quote_ident(_tablename3) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx3') || ' ON ' || quote_ident(_tablename3) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename3 || '_indx4') || ' ON ' || quote_ident(_tablename3) || '(beneficiary_type)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'beneficiary_type, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'sum(thr_eligible),' ||
		'sum(rations_21_plus_distributed), ' ||
		'2 ' ||
		'FROM ' || quote_ident(_tablename3) || ' ' ||
		'GROUP BY state_id, district_id, month, beneficiary_type)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx1') || ' ON ' || quote_ident(_tablename2) || '(state_id, district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx2') || ' ON ' || quote_ident(_tablename2) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename2 || '_indx3') || ' ON ' || quote_ident(_tablename2) || '(beneficiary_type)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || '(SELECT ' ||
		'state_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'beneficiary_type, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'sum(thr_eligible),' ||
		'sum(rations_21_plus_distributed), ' ||
		'1 ' ||
		'FROM ' || quote_ident(_tablename2) || ' ' ||
		'GROUP BY state_id, district_id, month, beneficiary_type)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx1') || ' ON ' || quote_ident(_tablename1) || '(state_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename1 || '_indx2') || ' ON ' || quote_ident(_tablename1) || '(beneficiary_type)';

END;
$BODY$
LANGUAGE plpgsql;

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
	_thr_tablename text;
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
	_thr_tablename := 'agg_thr_data' || '_' || _start_date;
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
		' (state_id, district_id, block_id, supervisor_id, awc_id, month, num_awcs, thr_score, thr_eligible_ccs, ' ||
		'thr_eligible_child, thr_rations_21_plus_distributed_ccs, thr_rations_21_plus_distributed_child, wer_score, pse_score, awc_not_open_no_data, is_launched, training_phase, aggregation_level) ' ||
		'(SELECT ' ||
			'state_id, ' ||
			'district_id, ' ||
			'block_id, ' ||
			'supervisor_id, ' ||
			'doc_id AS awc_id, ' ||
			quote_literal(_start_date) || ', ' ||
			'1, ' ||
			'0, ' ||
			'0, ' ||
			'0, ' ||
			'0, ' ||
			'0, ' ||
			'0, ' ||
			'0, ' ||
			'25, ' ||
			quote_literal(_no_text) || ', ' ||
            '0, ' ||
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
		'total_eligible_children = ut.total_eligible_children, ' ||
		'total_attended_children = ut.total_attended_children, ' ||
		'pse_avg_attendance_percent = ut.pse_avg_attendance_percent, ' ||
		'pse_full = ut.pse_full, ' ||
		'pse_partial = ut.pse_partial, ' ||
		'pse_non = ut.pse_non, ' ||
		'pse_score = ut.pse_score, ' ||
		'awc_days_provided_breakfast = ut.awc_days_provided_breakfast, ' ||
		'awc_days_provided_hotmeal = ut.awc_days_provided_hotmeal, ' ||
		'awc_days_provided_thr = ut.awc_days_provided_thr, ' ||
		'awc_days_provided_pse = ut.awc_days_provided_pse, ' ||
		'awc_not_open_holiday = ut.awc_not_open_holiday, ' ||
		'awc_not_open_festival = ut.awc_not_open_festival, ' ||
		'awc_not_open_no_help = ut.awc_not_open_no_help, ' ||
		'awc_not_open_department_work = ut.awc_not_open_department_work, ' ||
		'awc_not_open_other = ut.awc_not_open_other, ' ||
		'awc_not_open_no_data = ut.awc_not_open_no_data, ' ||
		'awc_num_open = ut.awc_num_open, ' ||
		'awc_days_pse_conducted = ut.awc_days_pse_conducted ' ||
	'FROM (SELECT ' ||
		'awc_id, ' ||
		'month, ' ||
		'sum(awc_open_count) AS awc_days_open, ' ||
		'sum(eligible_children) AS total_eligible_children, ' ||
		'sum(attended_children) AS total_attended_children, ' ||
		'avg(attended_children_percent) AS pse_avg_attendance_percent, ' ||
		'sum(attendance_full) AS pse_full, ' ||
		'sum(attendance_partial) AS pse_partial, ' ||
		'sum(attendance_non) AS pse_non, ' ||
		'CASE WHEN ((sum(attendance_full)::numeric * 1.25) + (0.625 * sum(attendance_partial)::numeric) + (0.0625 * sum(attendance_non)::numeric)) >= 20 THEN 20 ' ||
			'WHEN ((sum(attendance_full)::numeric * 1.25) + (0.625 * sum(attendance_partial)::numeric) + (0.0625 * sum(attendance_non)::numeric)) >= 10 THEN 10 ' ||
			'ELSE 1 END AS pse_score, ' ||
		'sum(open_bfast_count) AS awc_days_provided_breakfast, ' ||
		'sum(open_hotcooked_count) AS awc_days_provided_hotmeal, ' ||
		'sum(days_thr_provided_count) AS awc_days_provided_thr, ' ||
		'sum(open_pse_count) AS awc_days_provided_pse, ' ||
		'sum(awc_not_open_holiday) AS awc_not_open_holiday, ' ||
		'sum(awc_not_open_festival) AS awc_not_open_festival, ' ||
		'sum(awc_not_open_no_help) AS awc_not_open_no_help, ' ||
		'sum(awc_not_open_department_work) AS awc_not_open_department_work, ' ||
		'sum(awc_not_open_other) AS awc_not_open_other, ' ||
		'25 - sum(awc_open_count) AS awc_not_open_no_data, ' ||
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
		'wer_score = ut.wer_score, ' ||
		'thr_eligible_child = ut.thr_eligible_child, ' ||
		'thr_rations_21_plus_distributed_child = ut.thr_rations_21_plus_distributed_child ' ||
	'FROM (SELECT ' ||
		'awc_id, ' ||
		'month, ' ||
		'sum(valid_in_month) AS cases_child_health, ' ||
		'sum(valid_all_registered_in_month) AS cases_child_health_all, ' ||
		'sum(nutrition_status_weighed) AS wer_weighed, ' ||
		'sum(wer_eligible) AS wer_eligible, ' ||
		'CASE WHEN sum(wer_eligible) = 0 THEN 1 ' ||
			'WHEN (sum(nutrition_status_weighed)::numeric / sum(wer_eligible)) >= 0.8 THEN 20 ' ||
			'WHEN (sum(nutrition_status_weighed)::numeric / sum(wer_eligible)) >= 0.6 THEN 10 ' ||
			'ELSE 1 END AS wer_score, ' ||
		'sum(thr_eligible) AS thr_eligible_child, ' ||
		'sum(rations_21_plus_distributed) AS thr_rations_21_plus_distributed_child '
		'FROM ' || quote_ident(_child_health_tablename) || ' ' ||
		'WHERE month = ' || quote_literal(_start_date) || ' AND aggregation_level = 5 GROUP BY awc_id, month) ut ' ||
	'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

	-- Aggregate monthly ccs record table
	EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
		'cases_ccs_pregnant = ut.cases_ccs_pregnant, ' ||
		'cases_ccs_lactating = ut.cases_ccs_lactating, ' ||
		'cases_ccs_pregnant_all = ut.cases_ccs_pregnant_all, ' ||
		'cases_ccs_lactating_all = ut.cases_ccs_lactating_all, ' ||
		'thr_eligible_ccs = ut.thr_eligible_ccs, ' ||
		'thr_rations_21_plus_distributed_ccs = ut.thr_rations_21_plus_distributed_ccs ' ||
	'FROM (SELECT ' ||
		'awc_id, ' ||
		'month, ' ||
		'sum(pregnant) AS cases_ccs_pregnant, ' ||
		'sum(lactating) AS cases_ccs_lactating, ' ||
		'sum(pregnant_all) AS cases_ccs_pregnant_all, ' ||
		'sum(lactating_all) AS cases_ccs_lactating_all, ' ||
		'sum(thr_eligible) AS thr_eligible_ccs, ' ||
		'sum(rations_21_plus_distributed) AS thr_rations_21_plus_distributed_ccs '
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
		'cases_person_has_aadhaar = ut.cases_person_has_aadhaar, ' ||
		'cases_person_beneficiary = ut.cases_person_beneficiary, ' ||
		'cases_person_adolescent_girls_11_14 = ut.cases_person_adolescent_girls_11_14, ' ||
		'cases_person_adolescent_girls_11_14_all = ut.cases_person_adolescent_girls_11_14_all, ' ||
		'cases_person_adolescent_girls_15_18 = ut.cases_person_adolescent_girls_15_18, ' ||
		'cases_person_adolescent_girls_15_18_all = ut.cases_person_adolescent_girls_15_18_all, ' ||
		'cases_person_referred = ut.cases_person_referred ' ||
	'FROM (SELECT ' ||
		'awc_id, ' ||
		'sum(seeking_services) AS cases_person, ' ||
		'sum(count) AS cases_person_all, ' ||
		'sum(CASE WHEN aadhar_date <= ' || quote_literal(_end_date) ||
                  ' AND (' || quote_literal(_month_end_6yr) || ' <= dob ' ||
                  '      OR (sex = ' || quote_literal(_female) ||
                  '          AND dob BETWEEN ' || quote_literal(_month_end_49yr) || ' AND ' || quote_literal(_month_start_11yr) || '))' ||
                  ' AND (date_death IS NULL OR date_death >= ' || quote_literal(_end_date) || ')' ||
      ' THEN seeking_services ELSE 0 END) as cases_person_has_aadhaar, ' ||
		'sum(CASE WHEN (' || quote_literal(_month_end_6yr) || ' <= dob ' ||
                  '      OR (sex = ' || quote_literal(_female) ||
                  '          AND dob BETWEEN ' || quote_literal(_month_end_49yr) || ' AND ' || quote_literal(_month_start_11yr) || '))' ||
                  ' AND (date_death IS NULL OR date_death >= ' || quote_literal(_end_date) || ')' ||
      ' THEN seeking_services ELSE 0 END) as cases_person_beneficiary, ' ||
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
    'cases_person_beneficiary_v2 = ut.child_beneficiary ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'sum(has_aadhar_id) as child_has_aadhar, ' ||
    'count(*) as child_beneficiary ' ||
    'FROM ' || quote_ident(_child_health_monthly_tablename) || ' ' ||
    'WHERE valid_in_month = 1' ||
    'GROUP BY awc_id) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

  -- Update ccs_record cases_person_has_aadhaar and cases_person_beneficiary
  -- pregnant and lactating both imply that the case is open, alive and seeking services in the month
  EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'cases_person_has_aadhaar_v2 = cases_person_has_aadhaar_v2 + ut.ccs_has_aadhar, ' ||
    'cases_person_beneficiary_v2 = cases_person_beneficiary_v2 + ut.ccs_beneficiary ' ||
  'FROM (SELECT ' ||
    'awc_id, ' ||
    'sum(has_aadhar_id) as ccs_has_aadhar, ' ||
    'count(*) as ccs_beneficiary ' ||
    'FROM ' || quote_ident(_ccs_record_monthly_tablename) || ' ' ||
    'WHERE pregnant = 1 OR lactating = 1 ' ||
    'GROUP BY awc_id) ut ' ||
  'WHERE ut.awc_id = agg_awc.awc_id';

	-- Pass to combine THR information from ccs record and child health table
	EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' SET thr_score = ' ||
	'CASE WHEN ((thr_rations_21_plus_distributed_ccs + thr_rations_21_plus_distributed_child)::numeric / ' ||
		'(CASE WHEN (thr_eligible_child + thr_eligible_ccs) = 0 THEN 1 ELSE (thr_eligible_child + thr_eligible_ccs) END)) >= 0.7 THEN 20 ' ||
		'WHEN ((thr_rations_21_plus_distributed_ccs + thr_rations_21_plus_distributed_child)::numeric / ' ||
		'(CASE WHEN (thr_eligible_child + thr_eligible_ccs) = 0 THEN 1 ELSE (thr_eligible_child + thr_eligible_ccs) END)) >= 0.5 THEN 10 ' ||
		'ELSE 1 END';

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
		'awc_score, ' ||
		'num_awc_rank_functional, ' ||
		'num_awc_rank_semi, ' ||
		'num_awc_rank_non, ' ||
		'trained_phase_1, ' ||
		'trained_phase_2, ' ||
		'trained_phase_3, ' ||
		'trained_phase_4) = ' ||
	'(' ||
		'pse_score + thr_score + wer_score, ' ||
		'CASE WHEN (pse_score + thr_score + wer_score) >= 60 THEN 1 ELSE 0 END, ' ||
		'CASE WHEN ((pse_score + thr_score + wer_score) >= 40 AND (pse_score + thr_score + wer_score) < 60) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (pse_score + thr_score + wer_score) < 40 THEN 1 ELSE 0 END, ' ||
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
		'infra_adequate_space_pse = ut.infra_adequate_space_pse ' ||
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
		'has_adequate_space_pse AS infra_adequate_space_pse ' ||
		'FROM ' || quote_ident(_infra_tablename) || ' ' ||
		'WHERE month <= ' || quote_literal(_end_date) || ' ORDER BY awc_id, submitted_on DESC) ut ' ||
	'WHERE ut.awc_id = agg_awc.awc_id';
    -- could possibly add multicol indexes to make order by faster?

	EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'num_awc_infra_last_update = 1 WHERE infra_last_update_date IS NOT NULL';

	EXECUTE 'UPDATE ' || quote_ident(_tablename5) || ' agg_awc SET ' ||
    'num_awc_infra_last_update = 0 WHERE infra_last_update_date IS NULL';

	-- Roll Up by Location
	_rollup_text = 	'sum(num_awcs), ' ||
		'sum(awc_days_open), ' ||
		'sum(total_eligible_children), ' ||
		'sum(total_attended_children), ' ||
		'avg(pse_avg_attendance_percent), ' ||
		'sum(pse_full), ' ||
		'sum(pse_partial), ' ||
		'sum(pse_non), ' ||
		'avg(pse_score), ' ||
		'sum(awc_days_provided_breakfast), ' ||
		'avg(awc_days_provided_hotmeal), ' ||
		'sum(awc_days_provided_thr), ' ||
		'sum(awc_days_provided_pse), ' ||
		'sum(awc_not_open_holiday), ' ||
		'sum(awc_not_open_festival), ' ||
		'sum(awc_not_open_no_help), ' ||
		'sum(awc_not_open_department_work), ' ||
		'sum(awc_not_open_other), ' ||
		'sum(awc_num_open), ' ||
		'sum(awc_not_open_no_data), ' ||
		'sum(wer_weighed), ' ||
		'sum(wer_eligible), ' ||
		'avg(wer_score), ' ||
		'sum(thr_eligible_child), ' ||
		'sum(thr_rations_21_plus_distributed_child), ' ||
		'sum(thr_eligible_ccs), ' ||
		'sum(thr_rations_21_plus_distributed_ccs), ' ||
		'avg(thr_score), ' ||
		'avg(awc_score), ' ||
		'sum(num_awc_rank_functional), ' ||
		'sum(num_awc_rank_semi), ' ||
		'sum(num_awc_rank_non), ' ||
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
        'sum(cases_person_has_aadhaar), ' ||
        'sum(cases_ccs_pregnant_all), ' ||
        'sum(cases_ccs_lactating_all), ' ||
        'sum(cases_child_health_all), ' ||
        'sum(cases_person_adolescent_girls_11_14), ' ||
        'sum(cases_person_adolescent_girls_15_18), ' ||
        'sum(cases_person_adolescent_girls_11_14_all), ' ||
        'sum(cases_person_adolescent_girls_15_18_all), ' ||
        'sum(infra_infant_weighing_scale), ' ||
        'sum(cases_person_beneficiary), ' ||
        quote_nullable(_null_value) || ', ' ||
        quote_nullable(_null_value) || ', ' ||
        'sum(num_awc_infra_last_update), ' ||
        'sum(cases_person_has_aadhaar_v2 ), ' ||
        'sum(cases_person_beneficiary_v2) ';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename4) || '(SELECT ' ||
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

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename3) || '(SELECT ' ||
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

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename2) || '(SELECT ' ||
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

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename1) || '(SELECT ' ||
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


--Aggregate Location TABLE
CREATE OR REPLACE FUNCTION aggregate_location_table() RETURNS VOID AS
$BODY$
DECLARE
	all_text text;
	null_value text;
BEGIN
	all_text = 'All';
	null_value = NULL;

	EXECUTE 'INSERT INTO awc_location (SELECT ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		'supervisor_id, ' ||
		'supervisor_name, ' ||
		'supervisor_site_code, ' ||
		'block_id, ' ||
		'block_name, ' ||
		'block_site_code, ' ||
		'district_id, ' ||
		'district_name, ' ||
		'district_site_code, ' ||
		'state_id, ' ||
		'state_name, ' ||
		'state_site_code, ' ||
		'4, ' ||
		'block_map_location_name, ' ||
		'district_map_location_name, ' ||
		'state_map_location_name FROM awc_location GROUP BY ' ||
		'supervisor_id, supervisor_name, supervisor_site_code, ' ||
		'block_id, block_name, block_site_code,' ||
		'district_id, district_name, district_site_code,' ||
		'state_id, state_name, state_site_code, ' ||
		'block_map_location_name, district_map_location_name, state_map_location_name ' ||
		')';

	EXECUTE 'INSERT INTO awc_location (SELECT ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		'block_id, ' ||
		'block_name, ' ||
		'block_site_code, ' ||
		'district_id, ' ||
		'district_name, ' ||
		'district_site_code, ' ||
		'state_id, ' ||
		'state_name, ' ||
		'state_site_code, ' ||
		'3, ' ||
		'block_map_location_name, ' ||
		'district_map_location_name, ' ||
		'state_map_location_name FROM awc_location GROUP BY ' ||
		'block_id, block_name, block_site_code,' ||
		'district_id, district_name, district_site_code,' ||
		'state_id, state_name, state_site_code, ' ||
		'block_map_location_name, district_map_location_name, state_map_location_name ' ||
		')';

	EXECUTE 'INSERT INTO awc_location (SELECT ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		'district_id, ' ||
		'district_name, ' ||
		'district_site_code, ' ||
		'state_id, ' ||
		'state_name, ' ||
		'state_site_code, ' ||
		'2, ' ||
		quote_nullable(null_value) || ', ' ||
		'district_map_location_name, ' ||
		'state_map_location_name FROM awc_location GROUP BY ' ||
		'district_id, district_name, district_site_code,' ||
		'state_id, state_name, state_site_code, ' ||
		'district_map_location_name, state_map_location_name ' ||
		')';

	EXECUTE 'INSERT INTO awc_location (SELECT ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(all_text) || ', ' ||
		'state_id, ' ||
		'state_name, ' ||
		'state_site_code, ' ||
		'1, ' ||
		quote_nullable(null_value) || ', ' ||
		quote_nullable(null_value) || ', ' ||
		'state_map_location_name FROM awc_location GROUP BY ' ||
		'state_id, state_name, state_site_code, state_map_location_name ' ||
		')';
END;
$BODY$
LANGUAGE plpgsql;

-- Aggregate a single daily  for the AWC
-- Depends on generation of the agg_awc table
CREATE OR REPLACE FUNCTION aggregate_awc_daily(date) RETURNS VOID AS
$BODY$
DECLARE
	_table_date date;
	_current_month date;
	_tablename text;
	_table_columns text;
    _daily_attendance_tablename text;
    _all_text text;
    _null_value text;
    _rollup_text text;
    _rollup_text_2 text;
BEGIN
	_table_date = ($1)::DATE;
	_current_month = date_trunc('MONTH', $1)::DATE;
	_tablename = 'agg_awc_daily' || '_' || _table_date;
	_all_text = 'All';
	_null_value = NULL;

	-- Explicitly define the table columns for use in updates and aggregation
	_table_columns = '' ||
	    'state_id, ' ||
	    'district_id, ' ||
	    'block_id, ' ||
	    'supervisor_id, ' ||
	    'awc_id, ' ||
	    'aggregation_level, ' ||
	    'date, ' ||
	    'cases_household, ' ||
	    'cases_person, ' ||
	    'cases_person_all, ' ||
	    'cases_person_has_aadhaar, ' ||
	    'cases_person_beneficiary, ' ||
	    'cases_child_health, ' ||
	    'cases_child_health_all, ' ||
	    'cases_ccs_pregnant, ' ||
	    'cases_ccs_pregnant_all, ' ||
	    'cases_ccs_lactating, ' ||
	    'cases_ccs_lactating_all, ' ||
	    'cases_person_adolescent_girls_11_14, ' ||
	    'cases_person_adolescent_girls_15_18, ' ||
	    'cases_person_adolescent_girls_11_14_all, ' ||
	    'cases_person_adolescent_girls_15_18_all, ' ||
	    'daily_attendance_open, ' ||
	    'num_awcs, ' ||
	    'num_launched_states, ' ||
	    'num_launched_districts, ' ||
	    'num_launched_blocks, ' ||
	    'num_launched_supervisors, ' ||
	    'num_launched_awcs, ' ||
      'cases_person_has_aadhaar_v2, ' ||
      'cases_person_beneficiary_v2 ';

	-- DROP and create daily table
	EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename);
	EXECUTE 'CREATE TABLE ' || quote_ident(_tablename) || '(' ||
        'CHECK ( date = DATE ' || quote_literal(_table_date) || ' )' ||
	    ') INHERITS (agg_awc_daily)';

	-- Copy from the current month agg_awc table (skipping daily_attendance_open which will be a separate query)
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
	    '( '|| _table_columns || ') '
	     '(SELECT ' ||
	        'state_id, ' ||
            'district_id, ' ||
            'block_id, ' ||
            'supervisor_id, ' ||
            'awc_id, ' ||
            'aggregation_level, ' ||
            quote_literal(_table_date) || ', ' ||
            'cases_household, ' ||
            'cases_person, ' ||
            'cases_person_all, ' ||
            'cases_person_has_aadhaar, ' ||
            'cases_person_beneficiary, ' ||
            'cases_child_health, ' ||
            'cases_child_health_all, ' ||
            'cases_ccs_pregnant, ' ||
            'cases_ccs_pregnant_all, ' ||
            'cases_ccs_lactating, ' ||
            'cases_ccs_lactating_all, ' ||
            'cases_person_adolescent_girls_11_14, ' ||
            'cases_person_adolescent_girls_15_18, ' ||
            'cases_person_adolescent_girls_11_14_all, ' ||
            'cases_person_adolescent_girls_15_18_all, ' ||
            '0, ' ||
            'num_awcs, ' ||
            'num_launched_states, ' ||
            'num_launched_districts, ' ||
            'num_launched_blocks, ' ||
            'num_launched_supervisors, ' ||
            'num_launched_awcs, ' ||
            'cases_person_has_aadhaar_v2, ' ||
            'cases_person_beneficiary_v2 ' ||
         'FROM agg_awc WHERE aggregation_level = 5 AND month = ' || quote_literal(_current_month) ||
         ')';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx2') || ' ON ' || quote_ident(_tablename) || '(date)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx3') || ' ON ' || quote_ident(_tablename) || '(awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx4') || ' ON ' || quote_ident(_tablename) || '(supervisor_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx5') || ' ON ' || quote_ident(_tablename) || '(block_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx6') || ' ON ' || quote_ident(_tablename) || '(district_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx7') || ' ON ' || quote_ident(_tablename) || '(aggregation_level)';

	-- Aggregate daily attendance table.
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
		'daily_attendance_open = ut.daily_attendance_open ' ||
	'FROM (SELECT ' ||
		'awc_id, ' ||
		'pse_date, ' ||
		'sum(awc_open_count) AS daily_attendance_open ' ||
		'FROM daily_attendance WHERE pse_date = ' || quote_literal(_table_date) || ' ' ||
		'GROUP BY awc_id, pse_date) ut ' ||
	'WHERE ut.pse_date = agg_awc.date AND ut.awc_id = agg_awc.awc_id';

	-- Roll Up by Location
	_rollup_text = 	'sum(cases_household), ' ||
		'sum(cases_person), ' ||
		'sum(cases_person_all), ' ||
		'sum(cases_person_has_aadhaar), ' ||
		'sum(cases_person_beneficiary), ' ||
		'sum(cases_child_health), ' ||
		'sum(cases_child_health_all), ' ||
		'sum(cases_ccs_pregnant), ' ||
		'sum(cases_ccs_pregnant_all), ' ||
		'sum(cases_ccs_lactating), ' ||
		'sum(cases_ccs_lactating_all), ' ||
		'sum(cases_person_adolescent_girls_11_14), ' ||
		'sum(cases_person_adolescent_girls_15_18), ' ||
		'sum(cases_person_adolescent_girls_11_14_all), ' ||
		'sum(cases_person_adolescent_girls_15_18_all), ' ||
		'sum(daily_attendance_open), ' ||
		'sum(num_awcs), ';

  _rollup_text_2 = 'sum(cases_person_has_aadhaar_v2), ' ||
    'sum(cases_person_beneficiary_v2) ';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
	    '( '|| _table_columns || ') '
	    '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		quote_literal(_all_text) || ', ' ||
		'4, ' ||
		'date, ' ||
		_rollup_text ||
		'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (sum(num_launched_awcs) > 0) THEN 1 ELSE 0 END, ' ||
		'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE aggregation_level = 5 ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, date)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
	    '( '|| _table_columns || ') '
	    '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'3, ' ||
		'date, ' ||
		_rollup_text ||
		'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (sum(num_launched_supervisors) > 0) THEN 1 ELSE 0 END, ' ||
		'sum(num_launched_supervisors), ' ||
		'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE aggregation_level = 4 ' ||
		'GROUP BY state_id, district_id, block_id, date)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
	    '( '|| _table_columns || ') '
	    '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'2, ' ||
		'date, ' ||
		_rollup_text ||
		'CASE WHEN (sum(num_launched_blocks) > 0) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (sum(num_launched_blocks) > 0) THEN 1 ELSE 0 END, ' ||
		'sum(num_launched_blocks), ' ||
		'sum(num_launched_supervisors), ' ||
		'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE aggregation_level = 3 ' ||
		'GROUP BY state_id, district_id, date)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
	    '( '|| _table_columns || ') '
	    '(SELECT ' ||
		'state_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'1, ' ||
		'date, ' ||
		_rollup_text ||
		'CASE WHEN (sum(num_launched_districts) > 0) THEN 1 ELSE 0 END, ' ||
		'sum(num_launched_districts), ' ||
		'sum(num_launched_blocks), ' ||
		'sum(num_launched_supervisors), ' ||
		'sum(num_launched_awcs), ' ||
    _rollup_text_2 ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE aggregation_level = 2 ' ||
		'GROUP BY state_id, date)';

END;
$BODY$
LANGUAGE plpgsql;
