CREATE TABLE {temp_table} AS
  (SELECT supervisor_id,
          SUM(CASE
                WHEN thr_eligible IS NOT NULL THEN thr_eligible
                ELSE 0
              END) AS mother_thr_eligible,
          SUM(CASE
                WHEN num_rations_distributed IS NOT NULL
                     AND thr_eligible = 1
                     AND num_rations_distributed = 0 THEN 1
                ELSE 0
              END) AS mother_thr_0,
          SUM(CASE
                WHEN num_rations_distributed IS NOT NULL
                     AND thr_eligible = 1
                     AND num_rations_distributed BETWEEN 1 AND 7 THEN 1
                ELSE 0
              END) AS mother_thr_1_7,
          SUM(CASE
                WHEN num_rations_distributed IS NOT NULL
                     AND thr_eligible = 1
                     AND num_rations_distributed BETWEEN 8 AND 14 THEN 1
                ELSE 0
              END) AS mother_thr_8_14,
          SUM(CASE
                WHEN num_rations_distributed IS NOT NULL
                     AND thr_eligible = 1
                     AND num_rations_distributed BETWEEN 15 AND 21 THEN 1
                ELSE 0
              END) AS mother_thr_15_21,
          SUM(CASE
                WHEN num_rations_distributed IS NOT NULL
                     AND thr_eligible = 1
                     AND num_rations_distributed > 21 THEN 1
                ELSE 0
              END) AS mother_thr_gt_21
   FROM   "ccs_record_monthly" ccs_record
   WHERE  ( ccs_record.month = '{month}' )
   GROUP  BY supervisor_id);
