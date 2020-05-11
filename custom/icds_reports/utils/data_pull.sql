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
    WHERE ccs.month='2020-05-01' AND (ccs.lactating=1 OR ccs.pregnant=1) AND ccs.mobile_number IS NOT NULL AND ccs.mobile_number <> '' AND length(ccs.mobile_number)=10;

--                           QUERY PLAN
-- --------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 1
--    Tasks Shown: All
--    ->  Task
--          Node: host=100.71.184.226 port=6432 dbname=icds_ucr
--          ->  Result  (cost=0.00..0.00 rows=0 width=256)
--                One-Time Filter: false
-- (7 rows)
