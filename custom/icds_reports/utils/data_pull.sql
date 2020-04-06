SELECT awc_name, awc_site_code, supervisor_name, supervisor_site_code, block_name, block_site_code, district_name, district_site_code, state_name, state_site_code, aww_name, contact_phone_number
FROM awc_location
    WHERE aggregation_level=5
    AND (contact_phone_number<>'' OR contact_phone_number IS NOT NULL)
    AND state_is_test<>1
    AND district_is_test<>1
    AND block_is_test<>1
    AND supervisor_is_test<>1
    AND awc_is_test<>1;
-- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 1
--    Tasks Shown: All
--    ->  Task
--          Node: host=100.71.184.222 port=6432 dbname=icds_ucr
--          ->  Seq Scan on awc_location_102840 awc_location  (cost=0.00..91231.86 rows=599485 width=153)
--                Filter: (((contact_phone_number <> ''::text) OR (contact_phone_number IS NOT NULL)) AND (state_is_test <> 1) AND (district_is_test <> 1) AND (block_is_test <> 1) AND (supervisor_is_test <> 1) AND (awc_is_test <> 1) AND (aggregation_level = 5))
