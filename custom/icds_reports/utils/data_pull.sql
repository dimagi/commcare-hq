SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    ccs.person_name,
    ccs.ccs_status,
    ccs.mobile_number
    FROM ccs_record_monthly ccs
    LEFT JOIN "awc_location" awc
    ON (awc.doc_id = ccs.awc_id AND awc.supervisor_id = ccs.supervisor_id)
    WHERE ccs.month='2020-05-01'
        AND (ccs.lactating=1 OR ccs.pregnant=1)
        AND ccs.mobile_number IS NOT NULL
        AND ccs.mobile_number <> ''
        AND length(ccs.mobile_number)=10
        AND SUBSTRING(ccs.mobile_number, 1, 1) IN ('9', '8', '7', '6');


-- 
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Gather  (cost=1001.11..144323.67 rows=1 width=117)
--                Workers Planned: 4
--                ->  Nested Loop Left Join  (cost=1.10..143323.57 rows=1 width=117)
--                      ->  Parallel Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs  (cost=0.56..143320.79 rows=1 width=106)
--                            Index Cond: (month = '2020-05-01'::date)
--                            Filter: ((mobile_number IS NOT NULL) AND (mobile_number <> ''::text) AND ((lactating = 1) OR (pregnant = 1)) AND (length(mobile_number) = 10) AND (("substring"(mobile_number, 1, 1))::integer <= 9) AND (("substring"(mobile_number, 1, 1))::integer >= 6))
--                      ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..2.77 rows=1 width=140)
--                            Index Cond: (doc_id = ccs.awc_id)
--                            Filter: (supervisor_id = ccs.supervisor_id)
-- (14 rows)
