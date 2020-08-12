SELECT district_name,
       block_name,
       supervisor_name,
       awc_location.supervisor_id,
       awc_name,
       SUM(pse_eligible) AS lunch_eligible,
       SUM(CASE
               WHEN lunch_count IS NOT NULL
                    AND pse_eligible=1
                    AND lunch_count=0 THEN 1
               ELSE 0
           END) AS lunch_0,
       CASE
           WHEN SUM(pse_eligible) IS NOT NULL
                AND SUM(pse_eligible)>0 THEN SUM(CASE
                                                     WHEN lunch_count IS NOT NULL
                                                          AND pse_eligible=1
                                                          AND lunch_count=0 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(pse_eligible)*100
           ELSE 0
       END AS percent_0,
       SUM(CASE
               WHEN lunch_count IS NOT NULL
                    AND pse_eligible=1
                    AND lunch_count BETWEEN 1 AND 7 THEN 1
               ELSE 0
           END) AS lunch_1_7,
       CASE
           WHEN SUM(pse_eligible) IS NOT NULL
                AND SUM(pse_eligible)>0 THEN SUM(CASE
                                                     WHEN lunch_count IS NOT NULL
                                                          AND pse_eligible=1
                                                          AND lunch_count BETWEEN 1 AND 7 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(pse_eligible)*100
           ELSE 0
       END AS percent_1_7,
       SUM(CASE
               WHEN lunch_count IS NOT NULL
                    AND pse_eligible=1
                    AND lunch_count BETWEEN 8 AND 14 THEN 1
               ELSE 0
           END) AS lunch_8_14,
       CASE
           WHEN SUM(pse_eligible) IS NOT NULL
                AND SUM(pse_eligible)>0 THEN SUM(CASE
                                                     WHEN lunch_count IS NOT NULL
                                                          AND pse_eligible=1
                                                          AND lunch_count BETWEEN 8 AND 14 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(pse_eligible)*100
           ELSE 0
       END AS percent_8_14,
       SUM(CASE
               WHEN lunch_count IS NOT NULL
                    AND pse_eligible=1
                    AND lunch_count BETWEEN 15 AND 21 THEN 1
               ELSE 0
           END)AS lunch_15_21,
       CASE
           WHEN SUM(pse_eligible) IS NOT NULL
                AND SUM(pse_eligible)>0 THEN SUM(CASE
                                                     WHEN lunch_count IS NOT NULL
                                                          AND pse_eligible=1
                                                          AND lunch_count BETWEEN 15 AND 21 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(pse_eligible)*100
           ELSE 0
       END AS percent_15_21,
       SUM(CASE
               WHEN lunch_count IS NOT NULL
                    AND pse_eligible=1
                    AND lunch_count>21 THEN 1
               ELSE 0
           END) AS lunch_gt_21,
       CASE
           WHEN SUM(pse_eligible) IS NOT NULL
                AND SUM(pse_eligible)>0 THEN SUM(CASE
                                                     WHEN lunch_count IS NOT NULL
                                                          AND pse_eligible=1
                                                          AND lunch_count>21 THEN 1
                                                     ELSE 0
                                                 END)::float/SUM(pse_eligible)*100
           ELSE 0
       END AS percent_gt_21,
       month
FROM awc_location
INNER JOIN "child_health_monthly" child_health ON (awc_location.doc_id=child_health.awc_id
                                                  AND awc_location.state_id='{location_id}'
                                                  AND district_is_test=0
                                                  AND awc_location.supervisor_id=child_health.supervisor_id
                                                  AND child_health.month='{month}')
WHERE child_health.age_in_months>36
  AND aggregation_level=5
GROUP BY district_name,
         block_name,
         supervisor_name,
         awc_location.supervisor_id,
         awc_name,
         month
