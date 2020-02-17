SELECT district_name,
       block_name,
       supervisor_name,
       awc_location.supervisor_id,
       awc_name,
       SUM(CASE
               WHEN thr_eligible IS NOT NULL THEN thr_eligible
               ELSE 0
           END) AS mother_thr_eligible,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND thr_eligible=1
                    AND num_rations_distributed=0 THEN 1
               ELSE 0
           END) AS mother_thr_0,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND thr_eligible=1
                                                          AND num_rations_distributed=0 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_mother_thr_0,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND thr_eligible=1
                    AND num_rations_distributed BETWEEN 1 AND 7 THEN 1
               ELSE 0
           END) AS mother_thr_1_7,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND thr_eligible=1
                                                          AND num_rations_distributed BETWEEN 1 AND 7 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_mother_thr_1_7,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND thr_eligible=1
                    AND num_rations_distributed BETWEEN 8 AND 14 THEN 1
               ELSE 0
           END) AS mother_thr_8_14,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND thr_eligible=1
                                                          AND num_rations_distributed BETWEEN 8 AND 14 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_mother_thr_8_14,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND thr_eligible=1
                    AND num_rations_distributed BETWEEN 15 AND 21 THEN 1
               ELSE 0
           END) AS mother_thr_15_21,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND thr_eligible=1
                                                          AND num_rations_distributed BETWEEN 15 AND 21 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_mother_thr_15_21,
       SUM(CASE
               WHEN num_rations_distributed IS NOT NULL
                    AND thr_eligible=1
                    AND num_rations_distributed>21 THEN 1
               ELSE 0
           END) AS mother_thr_gt_21,
       CASE
           WHEN SUM(thr_eligible) IS NOT NULL
                AND SUM(thr_eligible)>0 THEN SUM(CASE
                                                     WHEN num_rations_distributed IS NOT NULL
                                                          AND thr_eligible=1
                                                          AND num_rations_distributed>21 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(thr_eligible)*100
           ELSE 0
       END AS percent_mother_thr_gt_21,
       month
FROM awc_location
INNER JOIN "ccs_record_monthly" ccs_record ON (awc_location.doc_id=ccs_record.awc_id
                                               AND awc_location.state_id='{location_id}'
                                               AND district_is_test=0
                                               AND awc_location.supervisor_id = ccs_record.supervisor_id
                                               AND pregnant=0
                                               AND lactating=1
                                               AND ccs_record.month = '{month}')
WHERE awc_location.aggregation_level=5
GROUP BY district_name,
         block_name,
         supervisor_name,
         awc_location.supervisor_id,
         awc_name,
         month
