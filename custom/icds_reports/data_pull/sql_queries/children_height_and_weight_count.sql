SELECT state_name,
       SUM(low_birth_weight_in_month)   AS "# Newborns with Low Birth Weight",
       SUM(weighed_and_born_in_month)   AS "Total Children Born and Weighed",
       CASE
         WHEN SUM(weighed_and_born_in_month) > 0 THEN Trunc((
         SUM(low_birth_weight_in_month) / SUM(weighed_and_born_in_month) ::
         FLOAT
                                                        * 100
                                                            ) :: NUMERIC, 2)
         ELSE 0
       END                              "% LBW",
       SUM(bf_at_birth)                 AS "# Children Breastfed at Birth",
       SUM(born_in_month)               AS "Total Children Born",
       CASE
         WHEN SUM(born_in_month) > 0 THEN Trunc((
         SUM(bf_at_birth) / SUM(born_in_month) :: FLOAT * 100 ) :: NUMERIC, 2)
         ELSE 0
       END                              "% EIBF",
       SUM(ebf_in_month)                AS
       "# Children (0-6m) Exclusively Breastfed",
       SUM(ebf_eligible)                AS "Total Children (0-6m)",
       CASE
         WHEN SUM(ebf_eligible) > 0 THEN Trunc((
         SUM(ebf_in_month) / SUM(ebf_eligible) :: FLOAT * 100 ) :: NUMERIC, 2)
         ELSE 0
       END                              "% EBF",
       SUM(nutrition_status_weighed)    AS "# Children (0-5y) Weighed",
       SUM(wer_eligible)                AS
       "Total Children (0-5y) Eligible for Weighing",
       CASE
         WHEN SUM(wer_eligible) > 0 THEN Trunc(
         ( SUM(nutrition_status_weighed) / SUM(wer_eligible) :: FLOAT * 100 ) ::
                                           NUMERIC, 2)
         ELSE 0
       END                              "Weighing Efficiency",
       SUM(height_measured_in_month)    AS
       "# Children (6m-5y) whose Height was Measured",
       SUM(height_eligible)             AS
       "Total Children (6m-5y) Eligible for Height Measurement",
       CASE
         WHEN SUM(height_eligible) > 0 THEN Trunc(
         ( SUM(height_measured_in_month) / SUM(height_eligible) :: FLOAT * 100 )
         ::
                                              NUMERIC, 2)
         ELSE 0
       END                              "Height Measurement Efficiency",
       SUM(rations_21_plus_distributed) AS
       "# Children (6-36) who got THR for at Least 21 Days",
       SUM(thr_eligible)                AS
       "Total Children (6-36) Eligible for THR",
       CASE
         WHEN SUM(thr_eligible) > 0 THEN Trunc(
         ( SUM(rations_21_plus_distributed) / SUM(thr_eligible) :: FLOAT * 100 )
         ::
                                           NUMERIC, 2)
         ELSE 0
       END                              "% THR (6-36m, at Least 21 Days)",
       SUM(cf_in_month)                 AS
       "# Children Initiated on Appropriate Complementary Feeding",
       SUM(cf_eligible)                 AS "Total Children (6-24m)",
       CASE
         WHEN SUM(cf_eligible) > 0 THEN Trunc((
         SUM(cf_in_month) / SUM(cf_eligible) ::
         FLOAT * 100 ) :: NUMERIC, 2)
         ELSE 0
       END                              "% CF"
FROM   agg_child_health_monthly
WHERE  month = '{month}'
       AND aggregation_level = 1
GROUP  BY state_name
