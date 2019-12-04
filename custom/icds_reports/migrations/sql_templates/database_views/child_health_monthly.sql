DROP VIEW IF EXISTS child_health_monthly_view CASCADE;
CREATE VIEW child_health_monthly_view AS
  SELECT
      child_health_monthly.case_id,
      awc_location_months.awc_id,
      awc_location_months.awc_name,
      awc_location_months.awc_site_code,
      awc_location_months.supervisor_id,
      awc_location_months.supervisor_name,
      awc_location_months.block_id,
      awc_location_months.block_name,
      awc_location_months.district_id,
      awc_location_months.state_id,
      awc_location_months."contact_phone_number" AS "aww_phone_number",
      child_health_monthly.person_name,
      child_health_monthly.mother_name,
      child_health_monthly.dob,
      child_health_monthly.sex,
      child_health_monthly.caste,
      child_health_monthly.disabled,
      child_health_monthly.minority,
      child_health_monthly.resident,
      awc_location_months.month,
      child_health_monthly.age_in_months,
      child_health_monthly.open_in_month,
      child_health_monthly.valid_in_month,
      child_health_monthly.nutrition_status_last_recorded,
      child_health_monthly.current_month_nutrition_status,
      child_health_monthly.pse_eligible,
      child_health_monthly.pse_days_attended,
      child_health_monthly.recorded_weight,
      child_health_monthly.recorded_height,
      child_health_monthly.current_month_stunting,
      child_health_monthly.current_month_wasting,
      child_health_monthly.thr_eligible,
      child_health_monthly.num_rations_distributed,
      GREATEST(child_health_monthly.fully_immunized_on_time, child_health_monthly.fully_immunized_late) AS fully_immunized,
      CASE WHEN child_health_monthly.current_month_nutrition_status = 'severely_underweight' THEN 1
          WHEN child_health_monthly.current_month_nutrition_status = 'moderately_underweight' THEN 2
          WHEN child_health_monthly.current_month_nutrition_status = 'normal' THEN 3
          ELSE 4 END AS current_month_nutrition_status_sort,
      CASE WHEN child_health_monthly.current_month_stunting = 'severe' THEN 1
          WHEN child_health_monthly.current_month_stunting = 'moderate' THEN 2
          WHEN child_health_monthly.current_month_stunting = 'normal' THEN 3
          ELSE 4 END AS current_month_stunting_sort,
      CASE WHEN child_health_monthly.current_month_wasting = 'severe' THEN 1
          WHEN child_health_monthly.current_month_wasting = 'moderate' THEN 2
          WHEN child_health_monthly.current_month_wasting = 'normal' THEN 3
          ELSE 4 END AS current_month_wasting_sort,
      CASE
        WHEN child_health_monthly.zscore_grading_hfa = 1 AND child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN 'severe'
        WHEN child_health_monthly.zscore_grading_hfa = 2 AND child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN 'moderate'
        WHEN child_health_monthly.zscore_grading_hfa = 3 AND child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN 'normal'
        ELSE '' END AS current_month_stunting_v2,
      CASE
        WHEN (child_health_monthly.zscore_grading_wfh = 1 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 1 AND child_health_monthly.muac_grading_recorded_in_month = 1) THEN 'severe'
        WHEN (child_health_monthly.zscore_grading_wfh = 2 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 2 AND child_health_monthly.muac_grading_recorded_in_month = 2) THEN 'moderate'
        WHEN (child_health_monthly.zscore_grading_wfh = 3 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 3 AND child_health_monthly.muac_grading_recorded_in_month = 3) THEN 'normal'
        ELSE '' END AS current_month_wasting_v2,
      CASE
        WHEN child_health_monthly.zscore_grading_hfa_recorded_in_month = 1 THEN child_health_monthly.zscore_grading_hfa
        ELSE 4 END AS current_month_stunting_v2_sort,
      CASE
        WHEN (child_health_monthly.zscore_grading_wfh = 1 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 1 AND child_health_monthly.muac_grading_recorded_in_month = 1) THEN 1
        WHEN (child_health_monthly.zscore_grading_wfh = 2 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 2 AND child_health_monthly.muac_grading_recorded_in_month = 2) THEN 2
        WHEN (child_health_monthly.zscore_grading_wfh = 3 AND child_health_monthly.zscore_grading_wfh_recorded_in_month = 1) OR (child_health_monthly.muac_grading = 3 AND child_health_monthly.muac_grading_recorded_in_month = 3) THEN 3
        ELSE 4 END AS current_month_wasting_v2_sort,
      child_health_monthly.mother_phone_number,
      child_health_monthly.due_list_date_1g_dpt_1,
      child_health_monthly.due_list_date_2g_dpt_2,
      child_health_monthly.due_list_date_3g_dpt_3,
      child_health_monthly.due_list_date_5g_dpt_booster,
      child_health_monthly.due_list_date_5g_dpt_booster1,
      child_health_monthly.due_list_date_7gdpt_booster_2,
      child_health_monthly.due_list_date_0g_hep_b_0,
      child_health_monthly.due_list_date_1g_hep_b_1,
      child_health_monthly.due_list_date_2g_hep_b_2,
      child_health_monthly.due_list_date_3g_hep_b_3,
      child_health_monthly.due_list_date_3g_ipv,
      child_health_monthly.due_list_date_4g_je_1,
      child_health_monthly.due_list_date_5g_je_2,
      child_health_monthly.due_list_date_5g_measles_booster,
      child_health_monthly.due_list_date_4g_measles,
      child_health_monthly.due_list_date_0g_opv_0,
      child_health_monthly.due_list_date_1g_opv_1,
      child_health_monthly.due_list_date_2g_opv_2,
      child_health_monthly.due_list_date_3g_opv_3,
      child_health_monthly.due_list_date_5g_opv_booster,
      child_health_monthly.due_list_date_1g_penta_1,
      child_health_monthly.due_list_date_2g_penta_2,
      child_health_monthly.due_list_date_3g_penta_3,
      child_health_monthly.due_list_date_1g_rv_1,
      child_health_monthly.due_list_date_2g_rv_2,
      child_health_monthly.due_list_date_3g_rv_3,
      child_health_monthly.due_list_date_4g_vit_a_1,
      child_health_monthly.due_list_date_5g_vit_a_2,
      child_health_monthly.due_list_date_6g_vit_a_3,
      child_health_monthly.due_list_date_6g_vit_a_4,
      child_health_monthly.due_list_date_6g_vit_a_5,
      child_health_monthly.due_list_date_6g_vit_a_6,
      child_health_monthly.due_list_date_6g_vit_a_7,
      child_health_monthly.due_list_date_6g_vit_a_8,
      child_health_monthly.due_list_date_7g_vit_a_9,
      child_health_monthly.due_list_date_anc_1,
      child_health_monthly.due_list_date_anc_2,
      child_health_monthly.due_list_date_anc_3,
      child_health_monthly.due_list_date_anc_4,
      child_health_monthly.due_list_date_tt_1,
      child_health_monthly.due_list_date_tt_2,
      child_health_monthly.due_list_date_tt_booster,
      child_health_monthly.due_list_date_1g_bcg

  FROM "public"."awc_location_months" "awc_location_months"
  JOIN "public"."child_health_monthly" "child_health_monthly" ON (
      ("awc_location_months"."month" = "child_health_monthly"."month") AND
      ("awc_location_months"."awc_id" = "child_health_monthly"."awc_id")
  );
