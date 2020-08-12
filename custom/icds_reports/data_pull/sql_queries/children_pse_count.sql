SELECT state_name,
       Sum(child_pse_0)     AS "# Children (3-6y) who Attended PSE for 0 Days",
       Sum(child_pse_1_7)   AS "# Children (3-6y) who Attended PSE for 1-7 Days",
       Sum(child_pse_8_14)  AS "# Children (3-6y) who Attended PSE for 8-14 Days",
       Sum(child_pse_15_21) AS "# Children (3-6y) who Attended PSE for 15-21 Days",
       Sum(child_pse_gt_21) AS "# Children (3-6y) who Attended PSE for >21 Days",
       Sum(pse_eligible)    AS "Total Children (3-6y) Eligible to Attend PSE"
FROM   temp_pse_data_pull t
       JOIN awc_location_local a
         ON a.supervisor_id = t.supervisor_id
WHERE  aggregation_level = 4
       AND state_is_test = 0
GROUP  BY state_name
