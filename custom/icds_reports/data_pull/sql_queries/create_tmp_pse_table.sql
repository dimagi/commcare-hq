CREATE TABLE {temp_table} AS
SELECT   supervisor_id,
         Sum(
         CASE
                  WHEN pse_days_attended IS NOT NULL
                  AND      pse_days_attended=0 THEN 1
                  ELSE 0
         END) AS child_pse_0,
         Sum(
         CASE
                  WHEN pse_days_attended IS NOT NULL
                  AND      pse_days_attended>0
                  AND      pse_days_attended<=7 THEN 1
                  ELSE 0
         END) AS child_pse_1_7,
         Sum(
         CASE
                  WHEN pse_days_attended IS NOT NULL
                  AND      pse_days_attended>=8
                  AND      pse_days_attended<=14 THEN 1
                  ELSE 0
         END)AS child_pse_8_14,
         Sum(
         CASE
                  WHEN pse_days_attended IS NOT NULL
                  AND      pse_days_attended>=15
                  AND      pse_days_attended<=21 THEN 1
                  ELSE 0
         END)AS child_pse_15_21,
         Sum(
         CASE
                  WHEN pse_days_attended IS NOT NULL
                  AND      pse_days_attended>21 THEN 1
                  ELSE 0
         END)              AS child_pse_gt_21,
         Sum(pse_eligible) AS pse_eligible
FROM     "child_health_monthly" child_health
WHERE    month='{month}'
AND      age_tranche::integer BETWEEN 37 AND      72
GROUP BY supervisor_id;
