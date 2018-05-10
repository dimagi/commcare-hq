
CREATE TABLE IF NOT EXISTS public."config_report_icds-cas_static-child_health_cases_a46c129f"
(
  doc_id text NOT NULL,
  inserted_at text,
  person_name text,
  modified_on date,
  opened_on date,
  closed_on date,
  closed integer,
  owner_id text,
  case_id text NOT NULL,
  household_id text NOT NULL,
  mother_id text,
  awc_id text NOT NULL,
  supervisor_id text,
  block_id text,
  district_id text,
  state_id text,
  dob date,
  sex text,
  zscore_grading_wfa text,
  open_count integer,
  birth_weight numeric(64,16),
  weighed_birth_open_count integer,
  lbw_open_count integer,
  last_date_gmp date,
  open_weighed integer,
  is_ebf_open_count integer,
  diet_diversity_open_count integer,
  diet_quantity_open_count integer,
  hand_washing_open_count integer,
  timely_bf_open_count integer,
  comp_feeding_yes_open_count integer,
  is_pretem_or_lbw_open_count integer,
  sev_mal_open_count integer,
  mod_mal_open_count integer,
  norm_mal_open_count integer,
  open_not_weighed_count integer,
  date_death date,
  age_at_death_yrs integer,
  dead_child_count integer,
  resident text,
  disabled text,
  caste text,
  minority text,
  name text,
  mother_name text,
  bf_at_birth text,
  fully_immunized_date date,
  CONSTRAINT "config_report_icds-cas_static-child_health_cases_a46c129f_pkey" PRIMARY KEY (doc_id, case_id)
);


DROP VIEW IF EXISTS child_health_monthly_view CASCADE;
CREATE VIEW child_health_monthly_view AS
    SELECT
        "child_list".case_id,
        "child_list".awc_id,
        "child_list".supervisor_id,
        "child_list".block_id,
        "child_list".district_id,
        "child_list".state_id,
        "child_list".name AS person_name,
        "child_list".mother_name,
        "child_list".dob,
        "child_list".sex,
        child_health_monthly.month,
        child_health_monthly.age_in_months,
        child_health_monthly.open_in_month,
        child_health_monthly.valid_in_month,
        child_health_monthly.nutrition_status_last_recorded,
        child_health_monthly.current_month_nutrition_status,
        child_health_monthly.pse_days_attended,
        child_health_monthly.recorded_weight,
        child_health_monthly.recorded_height,
        child_health_monthly.current_month_stunting,
        child_health_monthly.current_month_wasting,
        child_health_monthly.thr_eligible,
        GREATEST(child_health_monthly.fully_immunized_on_time, child_health_monthly.fully_immunized_late) AS fully_immunized,
        CASE WHEN child_health_monthly.current_month_nutrition_status = 'severely_underweight' THEN 1
            WHEN child_health_monthly.current_month_nutrition_status = 'moderately_underweight'  THEN 2
            WHEN child_health_monthly.current_month_nutrition_status = 'normal' THEN 3
            ELSE 4 END AS current_month_nutrition_status_sort,
        CASE WHEN child_health_monthly.current_month_stunting = 'severe' THEN 1
            WHEN child_health_monthly.current_month_stunting = 'moderate' THEN 2
            WHEN child_health_monthly.current_month_stunting = 'normal' THEN 3
            ELSE 4 END AS current_month_stunting_sort,
        CASE WHEN child_health_monthly.current_month_wasting = 'severe' THEN 1
            WHEN child_health_monthly.current_month_wasting = 'moderate'  THEN 2
            WHEN child_health_monthly.current_month_wasting = 'normal' THEN 3
            ELSE 4 END AS current_month_wasting_sort
   FROM "config_report_icds-cas_static-child_health_cases_a46c129f" "child_list"
     LEFT JOIN child_health_monthly child_health_monthly ON "child_list".doc_id = child_health_monthly.case_id
