SELECT state_name,
       SUM(nutrition_status_moderately_underweight)
       + SUM(nutrition_status_severely_underweight) AS
       "# Underweight Children (0-5y)",
       SUM(nutrition_status_weighed)                AS
       "Total Children (0-5y) Weighed",
       CASE
         WHEN SUM(nutrition_status_weighed) > 0 THEN Trunc(
         ( ( SUM(nutrition_status_moderately_underweight)
             + SUM(nutrition_status_severely_underweight) ) / SUM(
         nutrition_status_weighed) :: FLOAT * 100 ) :: NUMERIC, 2)
         ELSE 0
       END
       "% Underweight Children (0-5y)",
       SUM(zscore_grading_hfa_moderate)
       + SUM(zscore_grading_hfa_severe)             AS
       "# Stunted Children (0-5y)",
       SUM(zscore_grading_hfa_recorded_in_month)    AS
       "Total Children (0-5y) whose Height was Measured",
       CASE
         WHEN SUM(zscore_grading_hfa_recorded_in_month) > 0 THEN Trunc(
         ( ( SUM(zscore_grading_hfa_moderate)
             + SUM(zscore_grading_hfa_severe) ) / SUM(
         zscore_grading_hfa_recorded_in_month) :: FLOAT * 100 ) :: NUMERIC, 2)
         ELSE 0
       END
       "% Children (0-5y) with Stunting",
       SUM(wasting_moderate_v2)
       + SUM(wasting_severe_v2)                     AS
       "# Wasted Children (0-5y)",
       SUM(zscore_grading_wfh_recorded_in_month)    AS
       "Total Children (0-5y) whose Height and Weight was Measured",
       CASE
         WHEN SUM(zscore_grading_wfh_recorded_in_month) > 0 THEN
         Trunc((
                 ( SUM(wasting_moderate_v2)
                   + SUM(wasting_severe_v2) ) / SUM(
                 zscore_grading_wfh_recorded_in_month)
                 ::
                 FLOAT
                 * 100 ) :: NUMERIC, 2)
         ELSE 0
       END
       "% Children (0-5y) with Wasting"
FROM   agg_child_health_monthly
WHERE  month = '{month}'
       AND aggregation_level = 1
       AND ( age_tranche :: INTEGER <> 72
              OR age_tranche IS NULL )
GROUP  BY state_name
