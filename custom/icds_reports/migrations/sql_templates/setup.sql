-- Table: icds_months
CREATE TABLE "icds_months"
(
  month_name text NOT NULL,
  start_date date NOT NULL,
  end_date date NOT NULL,
  CONSTRAINT "pk_config_icds_months" PRIMARY KEY (month_name)
)
WITH (
  OIDS=FALSE
);

-- Table: awc_location
CREATE TABLE awc_location
(
  doc_id text NOT NULL,
  awc_name text,
  awc_site_code text,
  supervisor_id text,
  supervisor_name text,
  supervisor_site_code text,
  block_id text,
  block_name text,
  block_site_code text,
  district_id text,
  district_name text,
  district_site_code text,
  state_id text,
  state_name text,
  state_site_code text,
  aggregation_leve integer,
  block_map_location_name text,
  district_map_location_name text,
  state_map_location_name text,
  aww_name text,
  contact_phone_number text,
  state_is_test smallint,
  district_is_test smallint,
  block_is_test smallint,
  supervisor_is_test smallint,
  awc_is_test smallint,
  CONSTRAINT awc_location_pkey PRIMARY KEY (state_id, district_id, block_id, supervisor_id, doc_id)
);
CREATE INDEX awc_location_indx1 ON awc_location (aggregation_level);
CREATE INDEX awc_location_indx2 ON awc_location (state_id);
CREATE INDEX awc_location_indx3 ON awc_location (district_id);
CREATE INDEX awc_location_indx4 ON awc_location (block_id);
CREATE INDEX awc_location_indx5 ON awc_location (supervisor_id);
CREATE INDEX awc_location_indx6 ON awc_location (doc_id);

-- View: awc_location_months
CREATE OR REPLACE VIEW awc_location_months AS
 SELECT
	awc_location.doc_id as awc_id,
    awc_location.awc_name,
	awc_location.awc_site_code,
    awc_location.supervisor_id,
	awc_location.supervisor_name,
	awc_location.supervisor_site_code,
	awc_location.block_id,
	awc_location.block_name,
	awc_location.block_site_code,
	awc_location.district_id,
	awc_location.district_name,
	awc_location.district_site_code,
	awc_location.state_id,
	awc_location.state_name,
	awc_location.state_site_code,
    months.start_date AS month,
	months.month_name AS month_display
  FROM awc_location awc_location
  CROSS JOIN "icds_months" months;

-- Table: Table Name Mapping
CREATE TABLE ucr_table_name_mapping
(
	table_type text NOT NULL,
	table_name text NOT NULL,
	CONSTRAINT table_name_mapping_pkey PRIMARY KEY (table_type, table_name)
);

-- Table: agg_awc
CREATE TABLE agg_awc
(
  state_id text NOT NULL,
  district_id text NOT NULL,
  block_id text NOT NULL,
  supervisor_id text NOT NULL,
  awc_id text NOT NULL,
  month date NOT NULL,
  num_awcs integer NOT NULL,
  awc_days_open integer,
  total_eligible_children integer,
  total_attended_children integer,
  pse_avg_attendance_percent decimal,
  pse_full integer,
  pse_partial integer,
  pse_non integer,
  pse_score decimal,
  awc_days_provided_breakfast integer,
  awc_days_provided_hotmeal integer,
  awc_days_provided_thr integer,
  awc_days_provided_pse integer,
  awc_not_open_holiday integer,
  awc_not_open_festival integer,
  awc_not_open_no_help integer,
  awc_not_open_department_work integer,
  awc_not_open_other integer,
  awc_num_open integer,
  awc_not_open_no_data integer,
  wer_weighed integer,
  wer_eligible integer,
  wer_score decimal,
  thr_eligible_child integer,
  thr_rations_21_plus_distributed_child integer,
  thr_eligible_ccs integer,
  thr_rations_21_plus_distributed_ccs integer,
  thr_score decimal,
  awc_score decimal,
  num_awc_rank_functional integer,
  num_awc_rank_semi integer,
  num_awc_rank_non integer,
  cases_ccs_pregnant integer,
  cases_ccs_lactating integer,
  cases_child_health integer,
  usage_num_pse integer,
  usage_num_gmp integer,
  usage_num_thr integer,
  usage_num_home_visit integer,
  usage_num_bp_tri1 integer,
  usage_num_bp_tri2 integer,
  usage_num_bp_tri3 integer,
  usage_num_pnc integer,
  usage_num_ebf integer,
  usage_num_cf integer,
  usage_num_delivery integer,
  usage_num_due_list_ccs integer,
  usage_num_due_list_child_health integer,
  usage_awc_num_active integer,
  usage_time_pse decimal,
  usage_time_gmp decimal,
  usage_time_bp decimal,
  usage_time_pnc decimal,
  usage_time_ebf decimal,
  usage_time_cf decimal,
  usage_time_of_day_pse time,
  usage_time_of_day_home_visit time,
  vhnd_immunization integer,
  vhnd_anc integer,
  vhnd_gmp integer,
  vhnd_num_pregnancy integer,
  vhnd_num_lactating integer,
  vhnd_num_mothers_6_12 integer,
  vhnd_num_mothers_12 integer,
  vhnd_num_fathers integer,
  ls_supervision_visit integer,
  ls_num_supervised integer,
  ls_awc_location_long decimal,
  ls_awc_location_lat decimal,
  ls_awc_present integer,
  ls_awc_open integer,
  ls_awc_not_open_aww_not_available integer,
  ls_awc_not_open_closed_early integer,
  ls_awc_not_open_holiday integer,
  ls_awc_not_open_unknown integer,
  ls_awc_not_open_other integer,
  infra_last_update_date date,
  infra_type_of_building text,
  infra_type_of_building_pucca integer,
  infra_type_of_building_semi_pucca integer,
  infra_type_of_building_kuccha integer,
  infra_type_of_building_partial_covered_space integer,
  infra_clean_water integer,
  infra_functional_toilet integer,
  infra_baby_weighing_scale integer,
  infra_flat_weighing_scale integer,
  infra_adult_weighing_scale integer,
  infra_cooking_utensils integer,
  infra_medicine_kits integer,
  infra_adequate_space_pse integer
  usage_num_hh_reg integer,
  usage_num_add_person integer,
  usage_num_add_pregnancy integer,
  is_launched text,
  training_phase integer,
  trained_phase_1 integer,
  trained_phase_2 integer,
  trained_phase_3 integer,
  trained_phase_4 integer,
  aggregation_level integer,
  num_launched_states integer,
  num_launched_districts integer,
  num_launched_blocks integer,
  num_launched_supervisors integer,
  num_launched_awcs integer,
  cases_household integer,
  cases_person integer,
  cases_person_all integer,
  cases_person_has_aadhaar integer,
  cases_ccs_pregnant_all integer,
  cases_ccs_lactating_all integer,
  cases_child_health_all integer,
  cases_person_adolescent_girls_11_14 integer,
  cases_person_adolescent_girls_15_18 integer,
  cases_person_adolescent_girls_11_14_all integer,
  cases_person_adolescent_girls_15_18_all integer,
  infra_infant_weighing_scale integer,
  cases_person_beneficiary integer,
  cases_person_referred integer,
  awc_days_pse_conducted integer,
  num_awc_infra_last_update integer,
  cases_person_has_aadhaar_v2 integer,
  cases_person_beneficiary_v2 integer,
  electricity_awc integer,
  infantometer integer,
  stadiometer integer,
  num_anc_visits integer,
  num_children_immunized integer,
  state_is_test smallint,
  district_is_test smallint,
  block_is_test smallint,
  supervisor_is_test smallint,
  awc_is_test smallint,
  num_awcs_conducted_cbe integer,
  num_awcs_conducted_vhnd integer,
  valid_visits integer,
  expected_visits integer
);

-- Table: ccs_record_monthly
CREATE TABLE ccs_record_monthly
(
	awc_id text NOT NULL,
	case_id text NOT NULL,
	month date NOT NULL,
	age_in_months integer,
	ccs_status text,
	open_in_month integer,
	alive_in_month integer,
	trimester integer,
	num_rations_distributed integer,
	thr_eligible integer,
	tetanus_complete integer,
	delivered_in_month integer,
	anc1_received_at_delivery integer,
	anc2_received_at_delivery integer,
	anc3_received_at_delivery integer,
	anc4_received_at_delivery integer,
	registration_trimester_at_delivery integer,
	using_ifa integer,
	ifa_consumed_last_seven_days integer,
	anemic_severe integer,
	anemic_moderate integer,
	anemic_normal integer,
	anemic_unknown integer,
	extra_meal integer,
	resting_during_pregnancy integer,
	bp_visited_in_month integer,
	pnc_visited_in_month integer,
	trimester_2 integer,
	trimester_3 integer,
	counsel_immediate_bf integer,
	counsel_bp_vid integer,
	counsel_preparation integer,
	counsel_fp_vid integer,
	counsel_immediate_conception integer,
	counsel_accessible_postpartum_fp integer,
	bp1_complete integer,
	bp2_complete integer,
	bp3_complete integer,
	pnc_complete integer,
	postnatal integer,
    has_aadhar_id integer,
    counsel_fp_methods integer,
    pregnant integer,
    pregnant_all integer,
    lactating integer,
    lactating_all integer,
    institutional_delivery_in_month integer,
    add date,
    anc_in_month smallint,
    caste text,
    disabled text,
    minority text,
    resident text,
    anc_weight smallint,
    anc_blood_pressure smallint,
    bp_sys smallint,
    bp_dia smallint,
    anc_hemoglobin decimal,
    bleeding smallint,
    swelling smallint,
    blurred_vision smallint,
    convulsions smallint,
    rupture smallint,
    anemia smallint,
    eating_extra smallint,
    resting smallint,
    immediate_breastfeeding smallint,
    person_name text,
    edd date,
    delivery_nature smallint,
    is_ebf smallint,
    breastfed_at_birth smallint,
    anc_1 date,
    anc_2 date,
    anc_3 date,
    anc_4 date,
    tt_1 date,
    tt_2 date,
    valid_in_month smallint,
    preg_order smallint,
    mobile_number text,
    bp_date date,
    num_pnc_visits smallint,
    num_anc_complete smallint,
    last_date_thr date,
    opened_on date,
    home_visit_date date,
    dob date,
    valid_visits smallint,
    anc_abnormalities smallint,
    closed smallint,
    date_death date,
    person_case_id text,
    child_name text,
    institutional_delivery integer
);

-- Table: child_health_monthly
CREATE TABLE child_health_monthly
(
	awc_id text NOT NULL,
	case_id text NOT NULL,
	month date NOT NULL,
	age_in_months integer,
	open_in_month integer,
	alive_in_month integer,
	wer_eligible integer,
	nutrition_status_last_recorded text,
	current_month_nutrition_status text,
	nutrition_status_weighed integer,
	num_rations_distributed integer,
	pse_eligible integer,
	pse_days_attended integer,
	born_in_month integer,
	low_birth_weight_born_in_month integer,
	bf_at_birth_born_in_month integer,
	ebf_eligible integer,
	ebf_in_month integer,
	ebf_not_breastfeeding_reason text,
	ebf_drinking_liquid integer,
	ebf_eating integer,
	ebf_no_bf_no_milk integer,
	ebf_no_bf_pregnant_again integer,
	ebf_no_bf_child_too_old integer,
	ebf_no_bf_mother_sick integer,
	cf_eligible integer,
	cf_in_month integer,
	cf_diet_diversity integer,
	cf_diet_quantity integer,
	cf_handwashing integer,
	cf_demo integer,
	fully_immunized_eligible integer,
	fully_immunized_on_time integer,
	fully_immunized_late integer,
	counsel_ebf integer,
	counsel_adequate_bf integer,
	counsel_pediatric_ifa integer,
	counsel_comp_feeding_vid integer,
	counsel_increase_food_bf integer,
	counsel_manage_breast_problems integer,
	counsel_skin_to_skin integer,
	counsel_immediate_breastfeeding integer,
    recorded_weight decimal,
    recorded_height decimal,
    has_aadhar_id integer,
    thr_eligible integer,
    pnc_eligible integer,
    cf_initiation_in_month integer,
    cf_initiation_eligible integer,
    height_measured_in_month integer,
    current_month_stunting text,
    stunting_last_recorded text,
    wasting_last_recorded text,
    current_month_wasting text,
    valid_in_month integer,
    valid_all_registered_in_month integer,
    ebf_no_info_recorded integer,
    dob date,
    sex text,
    age_tranche text,
    caste text,
    disabled text,
    minority text,
    resident text,
    immunization_in_month smallint,
    days_ration_given_child smallint,
    zscore_grading_hfa smallint,
    zscore_grading_hfa_recorded_in_month smallint,
    zscore_grading_wfh smallint,
    zscore_grading_wfh_recorded_in_month smallint,
    muac_grading smallint,
    muac_grading_recorded_in_month smallint,
    person_name text,
    mother_name text,
    mother_phone_number text,
    date_death date,
    mother_case_id text,
    lunch_count integer
);

-- Table: agg_ccs_record
CREATE TABLE agg_ccs_record
(
  state_id text NOT NULL,
  district_id text NOT NULL,
  block_id text NOT NULL,
  supervisor_id text NOT NULL,
  awc_id text NOT NULL,
  month date NOT NULL,
  ccs_status text NOT NULL,
  trimester text,
  caste text,
  disabled text,
  minority text,
  resident text,
  valid_in_month integer NOT NULL,
  lactating integer NOT NULL,
  pregnant integer NOT NULL,
  thr_eligible integer NOT NULL,
  rations_21_plus_distributed integer NOT NULL,
  tetanus_complete integer NOT NULL,
  delivered_in_month integer NOT NULL,
  anc1_received_at_delivery integer NOT NULL,
  anc2_received_at_delivery integer NOT NULL,
  anc3_received_at_delivery integer NOT NULL,
  anc4_received_at_delivery integer NOT NULL,
  registration_trimester_at_delivery numeric,
  using_ifa integer NOT NULL,
  ifa_consumed_last_seven_days integer NOT NULL,
  anemic_normal integer NOT NULL,
  anemic_moderate integer NOT NULL,
  anemic_severe integer NOT NULL,
  anemic_unknown integer NOT NULL,
  extra_meal integer NOT NULL,
  resting_during_pregnancy integer NOT NULL,
  bp1_complete integer NOT NULL,
  bp2_complete integer NOT NULL,
  bp3_complete integer NOT NULL,
  pnc_complete integer NOT NULL,
  trimester_2 integer NOT NULL,
  trimester_3 integer NOT NULL,
  postnatal integer NOT NULL,
  counsel_bp_vid integer NOT NULL,
  counsel_preparation integer NOT NULL,
  counsel_immediate_bf integer NOT NULL,
  counsel_fp_vid integer NOT NULL,
  counsel_immediate_conception integer NOT NULL,
  counsel_accessible_postpartum_fp integer NOT NULL,
  has_aadhar_id integer,
  aggregation_level integer,
  valid_all_registered_in_month integer,
  institutional_delivery_in_month integer,
  lactating_all integer,
  pregnant_all integer,
  valid_visits int,
  expected_visits decimal,
  state_is_test smallint,
  district_is_test smallint,
  block_is_test smallint,
  supervisor_is_test smallint,
  awc_is_test smallint
);

-- Table: agg_child_health
CREATE TABLE agg_child_health
(
  state_id text NOT NULL,
  district_id text NOT NULL,
  block_id text NOT NULL,
  supervisor_id text NOT NULL,
  awc_id text NOT NULL,
  month date NOT NULL,
  gender text NOT NULL,
  age_tranche text NOT NULL,
  caste text NOT NULL,
  disabled text NOT NULL,
  minority text NOT NULL,
  resident text NOT NULL,
  valid_in_month integer NOT NULL,
  nutrition_status_weighed integer NOT NULL,
  nutrition_status_unweighed integer NOT NULL,
  nutrition_status_normal integer NOT NULL,
  nutrition_status_moderately_underweight integer NOT NULL,
  nutrition_status_severely_underweight integer NOT NULL,
  wer_eligible integer NOT NULL,
  thr_eligible integer NOT NULL,
  rations_21_plus_distributed integer NOT NULL,
  pse_eligible integer NOT NULL,
  pse_attended_16_days integer NOT NULL,
  born_in_month integer NOT NULL,
  low_birth_weight_in_month integer NOT NULL,
  bf_at_birth integer NOT NULL,
  ebf_eligible integer NOT NULL,
  ebf_in_month integer NOT NULL,
  cf_eligible integer NOT NULL,
  cf_in_month integer NOT NULL,
  cf_diet_diversity integer NOT NULL,
  cf_diet_quantity integer NOT NULL,
  cf_demo integer NOT NULL,
  cf_handwashing integer NOT NULL,
  counsel_increase_food_bf integer NOT NULL,
  counsel_manage_breast_problems integer NOT NULL,
  counsel_ebf integer NOT NULL,
  counsel_adequate_bf integer NOT NULL,
  counsel_pediatric_ifa integer NOT NULL,
  counsel_play_cf_video integer NOT NULL,
  fully_immunized_eligible integer NOT NULL,
  fully_immunized_on_time integer NOT NULL,
  fully_immunized_late integer NOT NULL
);
ALTER TABLE agg_child_health ALTER COLUMN age_tranche DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN disabled DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN resident DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN caste DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN minority DROP NOT NULL;
ALTER TABLE agg_child_health ALTER COLUMN gender DROP NOT NULL;
ALTER TABLE agg_child_health ADD COLUMN has_aadhar_id integer;
ALTER TABLE agg_child_health ADD COLUMN aggregation_level integer;
ALTER TABLE agg_child_health ADD COLUMN pnc_eligible integer;
ALTER TABLE agg_child_health ADD COLUMN height_eligible integer;
ALTER TABLE agg_child_health ADD COLUMN wasting_moderate integer;
ALTER TABLE agg_child_health ADD COLUMN wasting_severe integer;
ALTER TABLE agg_child_health ADD COLUMN stunting_moderate integer;
ALTER TABLE agg_child_health ADD COLUMN stunting_severe integer;
ALTER TABLE agg_child_health ADD COLUMN cf_initiation_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN cf_initiation_eligible integer;
ALTER TABLE agg_child_health ADD COLUMN height_measured_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN wasting_normal integer;
ALTER TABLE agg_child_health ADD COLUMN stunting_normal integer;
ALTER TABLE agg_child_health ADD COLUMN valid_all_registered_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN ebf_no_info_recorded integer;
ALTER TABLE agg_child_health ADD COLUMN weighed_and_height_measured_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN weighed_and_born_in_month integer;
ALTER TABLE agg_child_health ADD COLUMN days_ration_given_child integer;
ALTER TABLE agg_child_health ADD COLUMN zscore_grading_hfa_normal int;
ALTER TABLE agg_child_health ADD COLUMN zscore_grading_hfa_moderate int;
ALTER TABLE agg_child_health ADD COLUMN zscore_grading_hfa_severe int;
ALTER TABLE agg_child_health ADD COLUMN wasting_normal_v2 int;
ALTER TABLE agg_child_health ADD COLUMN wasting_moderate_v2 int;
ALTER TABLE agg_child_health ADD COLUMN wasting_severe_v2 int;
ALTER TABLE agg_child_health ADD COLUMN zscore_grading_hfa_recorded_in_month int ;
ALTER TABLE agg_child_health ADD COLUMN zscore_grading_wfh_recorded_in_month int ;
ALTER TABLE agg_child_health ADD COLUMN state_is_test smallint;
ALTER TABLE agg_child_health ADD COLUMN district_is_test smallint;
ALTER TABLE agg_child_health ADD COLUMN block_is_test smallint;
ALTER TABLE agg_child_health ADD COLUMN supervisor_is_test smallint;
ALTER TABLE agg_child_health ADD COLUMN awc_is_test smallint;
ALTER TABLE agg_child_health ADD COLUMN lunch_count_21_days integer;
ALTER TABLE agg_child_health ADD COLUMN pse_attended_21_days integer;

-- Table: daily_attendance
CREATE TABLE daily_attendance
(
  doc_id text NOT NULL,
  awc_id text,
  month date,
  pse_date date,
  awc_open_count integer,
  count integer,
  eligible_children integer,
  attended_children integer,
  attended_children_percent numeric,
  form_location text,
  form_location_lat numeric,
  form_location_long numeric,
  CONSTRAINT daily_attendance_pkey PRIMARY KEY (doc_id)
);
ALTER TABLE daily_attendance ADD COLUMN image_name text;
ALTER TABLE daily_attendance ADD COLUMN pse_conducted smallint ;
ALTER TABLE daily_attendance ADD COLUMN supervisor_id text;

CREATE TABLE agg_awc_daily
(
  state_id text NOT NULL,
  district_id text NOT NULL,
  block_id text NOT NULL,
  supervisor_id text NOT NULL,
  awc_id text NOT NULL,
  aggregation_level integer,
  date date NOT NULL,
  cases_household integer,
  cases_person integer,
  cases_person_all integer,
  cases_person_has_aadhaar integer,
  cases_child_health integer,
  cases_child_health_all integer,
  cases_ccs_pregnant integer,
  cases_ccs_pregnant_all integer,
  cases_ccs_lactating integer,
  cases_ccs_lactating_all integer,
  cases_person_adolescent_girls_11_14 integer,
  cases_person_adolescent_girls_15_18 integer,
  cases_person_adolescent_girls_11_14_all integer,
  cases_person_adolescent_girls_15_18_all integer,
  daily_attendance_open integer,
  num_awcs integer,
  num_launched_states integer,
  num_launched_districts integer,
  num_launched_blocks integer,
  num_launched_supervisors integer,
  num_launched_awcs integer
);
ALTER TABLE agg_awc_daily ADD COLUMN cases_person_beneficiary integer;
ALTER TABLE agg_awc_daily ADD COLUMN cases_person_has_aadhaar_v2 integer;
ALTER TABLE agg_awc_daily ADD COLUMN cases_person_beneficiary_v2 integer;
ALTER TABLE agg_awc_daily ADD COLUMN state_is_test smallint;
ALTER TABLE agg_awc_daily ADD COLUMN district_is_test smallint;
ALTER TABLE agg_awc_daily ADD COLUMN block_is_test smallint;
ALTER TABLE agg_awc_daily ADD COLUMN supervisor_is_test smallint;
ALTER TABLE agg_awc_daily ADD COLUMN awc_is_test smallint;

DROP FUNCTION IF EXISTS aggregate_awc_daily(date);
DROP FUNCTION IF EXISTS aggregate_awc_data(date);
DROP FUNCTION IF EXISTS aggregate_location_table();
DROP FUNCTION IF EXISTS update_location_table();
DROP FUNCTION IF EXISTS insert_into_daily_attendance(date);
DROP TABLE IF EXISTS agg_thr_data CASCADE;
DROP TABLE IF EXISTS ccs_record_categories CASCADE;
DROP TABLE IF EXISTS child_health_categories CASCADE;
DROP TABLE IF EXISTS india_geo_data CASCADE;
DROP TABLE IF EXISTS thr_categories CASCADE;
