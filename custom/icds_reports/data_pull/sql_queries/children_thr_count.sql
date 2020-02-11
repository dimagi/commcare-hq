SELECT state_name, 
       Sum(child_thr_0)     AS "# Children (6-36m) Given 0 Days THR", 
       Sum(child_thr_1_7)   AS "# Children (6-36m) Given 1-7 Days THR", 
       Sum(child_thr_8_14)  AS "# Children (6-36m) Given 8-14 Days THR", 
       Sum(child_thr_15_21) AS "# Children (6-36m) Given 15-21 Days THR", 
       Sum(child_thr_gt_21) AS "# Children (6-36m) Given >21 Days THR", 
       Sum(thr_eligible)    AS "Total # of Children (6-36m) Eligible for THR" 
FROM   temp_thr_data_pull t 
       JOIN awc_location_local a 
         ON a.supervisor_id = t.supervisor_id 
WHERE  aggregation_level = 4 
       AND state_is_test = 0 
GROUP  BY state_name 
