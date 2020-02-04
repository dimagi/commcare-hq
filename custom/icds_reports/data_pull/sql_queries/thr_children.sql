SELECT district_name,
       block_name,
       supervisor_name,
       awc_location.supervisor_id,
       awc_name,
       SUM(thr_eligible) AS thr_eligible,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND num_rations_distributed=0 THEN 1
               ELSE 0
           END) AS child_thr_0,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND num_rations_distributed=0 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_child_thr_0,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND num_rations_distributed BETWEEN 1 AND 7 THEN 1
               ELSE 0
           END) AS child_thr_1_7,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND num_rations_distributed BETWEEN 1 AND 7 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_child_thr_1_7,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND num_rations_distributed>=8
                    AND num_rations_distributed<=14 THEN 1
               ELSE 0
           END)AS child_thr_8_14,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND num_rations_distributed>=8
                                                          AND num_rations_distributed<=14 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_child_thr_8_14,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND num_rations_distributed>=15
                    AND num_rations_distributed<=21 THEN 1
               ELSE 0
           END)AS child_thr_15_21,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND num_rations_distributed>=15
                                                          AND num_rations_distributed<=21 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_child_thr_15_21,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND num_rations_distributed>21 THEN 1
               ELSE 0
           END) AS child_thr_gt_21,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND num_rations_distributed>21 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_child_thr_gt_21,
       month
FROM awc_location
INNER JOIN "child_health_monthly" child_health ON (awc_location.doc_id=child_health.awc_id
                                                  AND awc_location.state_id='{location_id}'
                                                  AND district_is_test=0
                                                  AND awc_location.supervisor_id = child_health.supervisor_id
                                                  AND child_health.month='{month}')
WHERE thr_eligible=1
  AND awc_location.aggregation_level=5
GROUP BY district_name,
         block_name,
         supervisor_name,
         awc_location.supervisor_id,
         awc_name,
         month
