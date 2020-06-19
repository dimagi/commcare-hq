CREATE TABLE {temp_table} AS
SELECT   supervisor_id,
         Sum(
         CASE
                  WHEN num_rations_distributed IS NOT NULL
                  AND      num_rations_distributed=0 THEN 1
                  ELSE 0
         END) AS child_thr_0,
         Sum(
         CASE
                  WHEN num_rations_distributed IS NOT NULL
                  AND      num_rations_distributed>0
                  AND      num_rations_distributed<=7 THEN 1
                  ELSE 0
         END) AS child_thr_1_7,
         Sum(
         CASE
                  WHEN num_rations_distributed IS NOT NULL
                  AND      num_rations_distributed>=8
                  AND      num_rations_distributed<=14 THEN 1
                  ELSE 0
         END)AS child_thr_8_14,
         Sum(
         CASE
                  WHEN num_rations_distributed IS NOT NULL
                  AND      num_rations_distributed>=15
                  AND      num_rations_distributed<=21 THEN 1
                  ELSE 0
         END)AS child_thr_15_21,
         Sum(
         CASE
                  WHEN num_rations_distributed IS NOT NULL
                  AND      num_rations_distributed>21 THEN 1
                  ELSE 0
         END)              AS child_thr_gt_21,
         Sum(thr_eligible) AS thr_eligible
FROM     "child_health_monthly" child_health
WHERE    month='{month}'
GROUP BY supervisor_id;
