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
		'state_site_code FROM ' || quote_ident(_ucr_location_table) || ')';
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
	EXECUTE 'CREATE TABLE ' || quote_ident(_tablename) || '() INHERITS ('  || quote_ident($1) || ')';
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
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
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
		'counsel_immediate_breastfeeding FROM ' || quote_ident(_ucr_child_monthly_table) || ' WHERE month = ' || quote_literal(_start_date) || ')';

		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id, case_id)';
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
		'postnatal FROM ' || quote_ident(_ucr_ccs_record_table) || ' WHERE month = ' || quote_literal(_start_date) || ')';

		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id, case_id)';
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
		'form_location_long ' ||
		'FROM ' || quote_ident(_daily_attendance_tablename) || ' WHERE month = ' || quote_literal(_start_date) || ')';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id)';
END;
$BODY$
LANGUAGE plpgsql;

-- Aggregate into agg_child_health
CREATE OR REPLACE FUNCTION aggregate_child_health(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
	_ucr_child_monthly_table text;
	_start_date date;
	_end_date date;
	_all_text text;
	_null_value text;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename := 'agg_child_health' || '_' || _start_date;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('child_health_monthly') INTO _ucr_child_monthly_table;
	_all_text = 'All';
	_null_value = NULL;

	EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id, ' ||
		'month, ' ||
		'sex, ' ||
		'age_tranche, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
		'sum(valid_in_month), ' ||
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
		'sum(fully_immunized_late) ' ||
		'FROM ' || quote_ident(_ucr_child_monthly_table) || ' WHERE month = ' || quote_literal(_start_date) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, sex, age_tranche, caste, disabled, minority, resident)';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx2') || ' ON ' || quote_ident(_tablename) || '(gender)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx3') || ' ON ' || quote_ident(_tablename) || '(age_tranche)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx4') || ' ON ' || quote_ident(_tablename) || '(month)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx5') || ' ON ' || quote_ident(_tablename) || '(caste)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx6') || ' ON ' || quote_ident(_tablename) || '(disabled)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx7') || ' ON ' || quote_ident(_tablename) || '(minority)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx8') || ' ON ' || quote_ident(_tablename) || '(resident)';

	--Roll up by category
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id,' ||
		'month, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'sum(valid_in_month), ' ||
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
		'sum(fully_immunized_late) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month)';


	--Roll up by location
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
		'sum(valid_in_month), ' ||
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
		'sum(fully_immunized_late) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, month, gender, age_tranche, caste, disabled, minority, resident)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
		'sum(valid_in_month), ' ||
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
		'sum(fully_immunized_late) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE awc_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, district_id, block_id, month, gender, age_tranche, caste, disabled, minority, resident)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
		'sum(valid_in_month), ' ||
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
		'sum(fully_immunized_late) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE supervisor_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, district_id, month, gender, age_tranche, caste, disabled, minority, resident)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'gender, ' ||
		'age_tranche, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
		'sum(valid_in_month), ' ||
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
		'sum(fully_immunized_late) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE block_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, month, gender, age_tranche, caste, disabled, minority, resident)';
END;
$BODY$
LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION aggregate_ccs_record(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
	_ucr_ccs_record_table text;
	_start_date date;
	_end_date date;
	_all_text text;
	_null_value text;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename := 'agg_ccs_record' || '_' || _start_date;
	_all_text = 'All';
	_null_value = NULL;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('ccs_record_monthly') INTO _ucr_ccs_record_table;

	EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id, ' ||
		'month, ' ||
		'ccs_status, ' ||
		'trimester, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
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
		'sum(counsel_accessible_postpartum_fp) ' ||
		'FROM ' || quote_ident(_ucr_ccs_record_table) || ' WHERE month = ' || quote_literal(_start_date) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, ccs_status, trimester, caste, disabled, minority, resident)';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx2') || ' ON ' || quote_ident(_tablename) || '(ccs_status)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx3') || ' ON ' || quote_ident(_tablename) || '(trimester)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx4') || ' ON ' || quote_ident(_tablename) || '(month)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx5') || ' ON ' || quote_ident(_tablename) || '(caste)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx6') || ' ON ' || quote_ident(_tablename) || '(disabled)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx7') || ' ON ' || quote_ident(_tablename) || '(minority)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx8') || ' ON ' || quote_ident(_tablename) || '(resident)';

	--Roll up by category
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id,' ||
		'month, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
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
		'sum(counsel_accessible_postpartum_fp) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month)';

	--Roll up by location
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		'trimester, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
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
		'sum(counsel_accessible_postpartum_fp) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, month, ccs_status, trimester, caste, disabled, minority, resident)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		'trimester, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
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
		'sum(counsel_accessible_postpartum_fp) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE awc_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, district_id, block_id, month, ccs_status, trimester, caste, disabled, minority, resident)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		'trimester, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
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
		'sum(counsel_accessible_postpartum_fp) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE supervisor_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, district_id, month, ccs_status, trimester, caste, disabled, minority, resident)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'ccs_status, ' ||
		'trimester, ' ||
		'caste, ' ||
		'disabled, ' ||
		'minority, ' ||
		'resident, ' ||
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
		'sum(counsel_accessible_postpartum_fp) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE block_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, month, ccs_status, trimester, caste, disabled, minority, resident)';
END;
$BODY$
LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION aggregate_thr_data(date) RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
	_child_health_tablename text;
	_ccs_record_tablename text;
	_start_date date;
	_all_text text;
	_null_value text;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_tablename := 'agg_thr_data' || '_' || _start_date;
	_child_health_tablename := 'agg_child_health' || '_' || _start_date;
	_ccs_record_tablename := 'agg_ccs_record' || '_' || _start_date;
	_all_text = 'All';
	_null_value = NULL;

	EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
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
		'sum(rations_21_plus_distributed) ' ||
		'FROM ' || quote_ident(_child_health_tablename) || ' WHERE caste != ' || quote_literal('All') || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, caste, disabled, minority, resident)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
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
		'sum(rations_21_plus_distributed) ' ||
		'FROM ' || quote_ident(_ccs_record_tablename) || ' WHERE caste != ' || quote_literal('All') || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month, ccs_status, caste, disabled, minority, resident)';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx2') || ' ON ' || quote_ident(_tablename) || '(beneficiary_type)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx3') || ' ON ' || quote_ident(_tablename) || '(month)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx4') || ' ON ' || quote_ident(_tablename) || '(caste)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx5') || ' ON ' || quote_ident(_tablename) || '(disabled)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx6') || ' ON ' || quote_ident(_tablename) || '(minority)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx7') || ' ON ' || quote_ident(_tablename) || '(resident)';

	--Roll up by category
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		'awc_id,' ||
		'month, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'sum(thr_eligible), ' ||
		'sum(rations_21_plus_distributed) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, awc_id, month)';


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
	_tablename text;
	_child_health_tablename text;
	_ccs_record_tablename text;
	_daily_attendance_tablename text;
	_awc_location_tablename text;
	_thr_tablename text;
	_usage_tablename text;
	_vhnd_tablename text;
	_ls_tablename text;
	_infra_tablename text;
	_all_text text;
	_null_value text;
BEGIN
	_start_date = date_trunc('MONTH', $1)::DATE;
	_end_date = (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 day')::DATE;
	_all_text = 'All';
	_null_value = NULL;
	_tablename := 'agg_awc' || '_' || _start_date;
	_child_health_tablename := 'agg_child_health' || '_' || _start_date;
	_ccs_record_tablename := 'agg_ccs_record' || '_' || _start_date;
	_thr_tablename := 'agg_thr_data' || '_' || _start_date;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('daily_feeding') INTO _daily_attendance_tablename;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('awc_location') INTO _awc_location_tablename;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('usage') INTO _usage_tablename;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('vhnd') INTO _vhnd_tablename;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('awc_mgmt') INTO _ls_tablename;
	EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('infrastructure') INTO _infra_tablename;

	-- Setup base locations and month
	EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) ||
		' (state_id, district_id, block_id, supervisor_id, awc_id, month, num_awcs, thr_score, thr_eligible_ccs, ' ||
		'thr_eligible_child, thr_rations_21_plus_distributed_ccs, thr_rations_21_plus_distributed_child, wer_score, pse_score) ' ||
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
			'0 ' ||
		'FROM ' || quote_ident(_awc_location_tablename) ||')';

	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(state_id, district_id, block_id, supervisor_id, awc_id)';
	EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx2') || ' ON ' || quote_ident(_tablename) || '(month)';

	-- Aggregate daily attendance table.  Not using monthly table as it doesn't have all indicators
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
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
		'awc_num_open = ut.awc_num_open ' ||
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
		'CASE WHEN (sum(awc_open_count) > 0) THEN 1 ELSE 0 END AS awc_num_open ' ||
		'FROM ' || quote_ident(_daily_attendance_tablename) || ' ' ||
		'WHERE month = ' || quote_literal(_start_date) || ' GROUP BY awc_id, month) ut ' ||
	'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

	-- Aggregate monthly child health table
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
		'cases_child_health = ut.cases_child_health, ' ||
		'wer_weighed = ut.wer_weighed, ' ||
		'wer_eligible = ut.wer_eligible, ' ||
		'wer_score = ut.wer_score, ' ||
		'thr_eligible_child = ut.thr_eligible_child, ' ||
		'thr_rations_21_plus_distributed_child = ut.thr_rations_21_plus_distributed_child ' ||
	'FROM (SELECT ' ||
		'awc_id, ' ||
		'month, ' ||
		'sum(valid_in_month) AS cases_child_health, ' ||
		'sum(nutrition_status_weighed) AS wer_weighed, ' ||
		'sum(wer_eligible) AS wer_eligible, ' ||
		'CASE WHEN sum(wer_eligible) = 0 THEN 1 ' ||
			'WHEN (sum(nutrition_status_weighed)::numeric / sum(wer_eligible)) >= 0.8 THEN 20 ' ||
			'WHEN (sum(nutrition_status_weighed)::numeric / sum(wer_eligible)) >= 0.6 THEN 10 ' ||
			'ELSE 1 END AS wer_score, ' ||
		'sum(thr_eligible) AS thr_eligible_child, ' ||
		'sum(rations_21_plus_distributed) AS thr_rations_21_plus_distributed_child '
		'FROM ' || quote_ident(_child_health_tablename) || ' ' ||
		'WHERE month = ' || quote_literal(_start_date) || ' AND caste != ' || quote_literal(_all_text) || ' GROUP BY awc_id, month) ut ' ||
	'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

	-- Aggregate monthly ccs record table
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
		'cases_ccs_pregnant = ut.cases_ccs_pregnant, ' ||
		'cases_ccs_lactating = ut.cases_ccs_lactating, ' ||
		'thr_eligible_ccs = ut.thr_eligible_ccs, ' ||
		'thr_rations_21_plus_distributed_ccs = ut.thr_rations_21_plus_distributed_ccs ' ||
	'FROM (SELECT ' ||
		'awc_id, ' ||
		'month, ' ||
		'sum(pregnant) AS cases_ccs_pregnant, ' ||
		'sum(lactating) AS cases_ccs_lactating, ' ||
		'sum(thr_eligible) AS thr_eligible_ccs, ' ||
		'sum(rations_21_plus_distributed) AS thr_rations_21_plus_distributed_ccs '
		'FROM ' || quote_ident(_ccs_record_tablename) || ' ' ||
		'WHERE month = ' || quote_literal(_start_date) || ' AND caste != ' || quote_literal(_all_text) || ' GROUP BY awc_id, month) ut ' ||
	'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';

	-- Pass to combine THR information from ccs record and child health table
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' SET thr_score = ' ||
	'CASE WHEN ((thr_rations_21_plus_distributed_ccs + thr_rations_21_plus_distributed_child)::numeric / ' ||
		'(CASE WHEN (thr_eligible_child + thr_eligible_ccs) = 0 THEN 1 ELSE (thr_eligible_child + thr_eligible_ccs) END)) >= 0.7 THEN 20 ' ||
		'WHEN ((thr_rations_21_plus_distributed_ccs + thr_rations_21_plus_distributed_child)::numeric / ' ||
		'(CASE WHEN (thr_eligible_child + thr_eligible_ccs) = 0 THEN 1 ELSE (thr_eligible_child + thr_eligible_ccs) END)) >= 0.5 THEN 10 ' ||
		'ELSE 1 END';

	-- Pass to calculate awc score and ranks
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' SET (' ||
		'awc_score, ' ||
		'num_awc_rank_functional, ' ||
		'num_awc_rank_semi, ' ||
		'num_awc_rank_non) = ' ||
	'(' ||
		'pse_score + thr_score + wer_score, ' ||
		'CASE WHEN (pse_score + thr_score + wer_score) >= 60 THEN 1 ELSE 0 END, ' ||
		'CASE WHEN ((pse_score + thr_score + wer_score) >= 40 AND (pse_score + thr_score + wer_score) < 40) THEN 1 ELSE 0 END, ' ||
		'CASE WHEN (pse_score + thr_score + wer_score) < 40 THEN 1 ELSE 0 END' ||
	')';

	-- Aggregate data from usage table
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
		'usage_num_pse = ut.usage_num_pse, ' ||
		'usage_num_gmp = ut.usage_num_gmp, ' ||
		'usage_num_thr = ut.usage_num_thr, ' ||
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
		'sum(home_visit) AS usage_num_home_visit, ' ||
		'sum(bp_tri1) AS usage_num_bp_tri1, ' ||
		'sum(bp_tri2) AS usage_num_bp_tri2, ' ||
		'sum(bp_tri3) AS usage_num_bp_tri3, ' ||
		'sum(pnc) AS usage_num_pnc, ' ||
		'sum(ebf) AS usage_num_ebf, ' ||
		'sum(cf) AS usage_num_cf, ' ||
		'sum(delivery) AS usage_num_delivery, ' ||
		'CASE WHEN (sum(pse) + sum(gmp) + sum(thr) + sum(home_visit)) >= 15 THEN 1 ELSE 0 END AS usage_awc_num_active, ' ||
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

	-- Aggregate data from VHND table
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
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
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
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
		'location_id AS awc_id, ' ||
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
		'WHERE month = ' || quote_literal(_start_date) || ' GROUP BY location_id, month) ut ' ||
	'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';


	-- Get latest infrastructure data
	EXECUTE 'UPDATE ' || quote_ident(_tablename) || ' agg_awc SET ' ||
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
		'adult_scale_available AS infra_adult_weighing_scale, ' ||
		'cooking_utensils_usable AS infra_cooking_utensils, ' ||
		'medicine_kits_usable AS infra_medicine_kits, ' ||
		'has_adequate_space_pse AS infra_adequate_space_pse ' ||
		'FROM ' || quote_ident(_infra_tablename) || ' ' ||
		'WHERE month <= ' || quote_literal(_end_date) || ' ORDER BY awc_id, submitted_on DESC) ut ' ||
	'WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id';


	-- Roll Up by Location
	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		'supervisor_id, ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'sum(num_awcs), ' ||
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
		'sum(infra_cooking_utensils), ' ||
		'sum(infra_medicine_kits), ' ||
		'sum(infra_adequate_space_pse) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'GROUP BY state_id, district_id, block_id, supervisor_id, month)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		'block_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'sum(num_awcs), ' ||
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
		'sum(infra_cooking_utensils), ' ||
		'sum(infra_medicine_kits), ' ||
		'sum(infra_adequate_space_pse) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE awc_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, district_id, block_id, month)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		'district_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'sum(num_awcs), ' ||
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
		'sum(infra_cooking_utensils), ' ||
		'sum(infra_medicine_kits), ' ||
		'sum(infra_adequate_space_pse) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE supervisor_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, district_id, month)';

	EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || '(SELECT ' ||
		'state_id, ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		quote_literal(_all_text) || ', ' ||
		'month, ' ||
		'sum(num_awcs), ' ||
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
		'sum(infra_cooking_utensils), ' ||
		'sum(infra_medicine_kits), ' ||
		'sum(infra_adequate_space_pse) ' ||
		'FROM ' || quote_ident(_tablename) || ' ' ||
		'WHERE block_id = ' || quote_literal(_all_text) || ' ' ||
		'GROUP BY state_id, month)';

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
		'state_site_code FROM awc_location GROUP BY ' ||
		'supervisor_id, supervisor_name, supervisor_site_code, ' ||
		'block_id, block_name, block_site_code,' ||
		'district_id, district_name, district_site_code,' ||
		'state_id, state_name, state_site_code' ||
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
		'state_site_code FROM awc_location GROUP BY ' ||
		'block_id, block_name, block_site_code,' ||
		'district_id, district_name, district_site_code,' ||
		'state_id, state_name, state_site_code' ||
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
		'state_site_code FROM awc_location GROUP BY ' ||
		'district_id, district_name, district_site_code,' ||
		'state_id, state_name, state_site_code' ||
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
		'state_site_code FROM awc_location GROUP BY ' ||
		'state_id, state_name, state_site_code' ||
		')';
END;
$BODY$
LANGUAGE plpgsql;
