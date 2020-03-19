SELECT state_name,
       Sum(mother_thr_0)        AS "# PW and LM Given 0 Days THR",
       Sum(mother_thr_1_7)      AS "# PW and LM Given 1-7 Days THR",
       Sum(mother_thr_8_14)     AS "# PW and LM Given 8-14 Days THR",
       Sum(mother_thr_15_21)    AS "# PW and LM Given 15-21 Days THR",
       Sum(mother_thr_gt_21)    AS "# PW and LM Given >21 Days THR",
       Sum(mother_thr_eligible) AS "Total # of PW and LM Eligible for THR"
FROM   dummy_thr_table t
       JOIN awc_location_local a
         ON a.supervisor_id = t.supervisor_id
WHERE  aggregation_level = 4
       AND state_is_test = 0
GROUP  BY state_name
