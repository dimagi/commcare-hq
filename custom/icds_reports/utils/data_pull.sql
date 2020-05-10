

SELECT caste, count(*) as number_0_3_child FROM "child_health_monthly" WHERE
    month='2020-05-01'
    AND age_tranche IN ('0', '6', '12', '24', '36')
    AND valid_in_month=1
    AND alive_in_month=1
    AND state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY caste;

--                                                                                                                        QUERY PLAN
-- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=75360.60..75462.39 rows=200 width=12)
--                      Group Key: child_health_monthly.caste
--                      ->  Gather Merge  (cost=75360.60..75456.39 rows=800 width=12)
--                            Workers Planned: 4
--                            ->  Sort  (cost=74360.55..74361.05 rows=200 width=12)
--                                  Sort Key: child_health_monthly.caste
--                                  ->  Partial HashAggregate  (cost=74350.90..74352.90 rows=200 width=12)
--                                        Group Key: child_health_monthly.caste
--                                        ->  Parallel Append  (cost=0.00..74244.24 rows=21332 width=4)
--                                              ->  Parallel Seq Scan on "child_health_monthly_2020-05-01_671996" child_health_monthly  (cost=0.00..74137.58 rows=21332 width=4)
--                                                    Filter: ((month = '2020-05-01'::date) AND (valid_in_month = 1) AND (alive_in_month = 1) AND (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text) AND (age_tranche = ANY ('{0,6,12,24,36}'::text[])))

SELECT caste, count(*) as number_3_6_child FROM "child_health_monthly" WHERE
    month='2020-05-01'
    AND age_tranche IN ('48', '60', '72')
    AND valid_in_month=1
    AND alive_in_month=1
    AND state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY caste;

-- QUERY PLAN
-- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=74808.50..74910.29 rows=200 width=12)
--                      Group Key: child_health_monthly.caste
--                      ->  Gather Merge  (cost=74808.50..74904.29 rows=800 width=12)
--                            Workers Planned: 4
--                            ->  Sort  (cost=73808.44..73808.94 rows=200 width=12)
--                                  Sort Key: child_health_monthly.caste
--                                  ->  Partial HashAggregate  (cost=73798.80..73800.80 rows=200 width=12)
--                                        Group Key: child_health_monthly.caste
--                                        ->  Parallel Append  (cost=0.00..73679.12 rows=23937 width=4)
--                                              ->  Parallel Seq Scan on "child_health_monthly_2020-05-01_671996" child_health_monthly  (cost=0.00..73559.43 rows=23937 width=4)
--                                                    Filter: ((month = '2020-05-01'::date) AND (valid_in_month = 1) AND (alive_in_month = 1) AND (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text) AND (age_tranche = ANY ('{48,60,72}'::text[])))

SELECT ccs.caste, count(*) as number_pw FROM "ccs_record_monthly" ccs
    LEFT JOIN "awc_location" awc ON awc.doc_id = ccs.awc_id
    WHERE ccs.month='2020-05-01' AND ccs.pregnant_all=1 AND ccs.valid_in_month=1 AND ccs.alive_in_month=1 AND awc.state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY ccs.caste;
--
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=157405.87..157415.12 rows=4 width=12)
--                      Group Key: ccs.caste
--                      ->  Gather Merge  (cost=157405.87..157415.00 rows=16 width=12)
--                            Workers Planned: 4
--                            ->  Partial GroupAggregate  (cost=156405.81..156413.04 rows=4 width=12)
--                                  Group Key: ccs.caste
--                                  ->  Sort  (cost=156405.81..156408.20 rows=959 width=4)
--                                        Sort Key: ccs.caste
--                                        ->  Nested Loop  (cost=1.10..156358.31 rows=959 width=4)
--                                              ->  Parallel Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs  (cost=0.56..143525.91 rows=5576 width=37)
--                                                    Index Cond: (month = '2020-05-01'::date)
--                                                    Filter: ((pregnant_all = 1) AND (valid_in_month = 1) AND (alive_in_month = 1))
--                                              ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..2.29 rows=1 width=31)
--                                                    Index Cond: (doc_id = ccs.awc_id)
--                                                    Filter: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)

SELECT ccs.caste, count(*) as number_lm FROM "ccs_record_monthly" ccs
    LEFT JOIN "awc_location" awc ON awc.doc_id = ccs.awc_id
    WHERE ccs.month='2020-05-01' AND ccs.lactating_all=1 AND ccs.valid_in_month=1 AND ccs.alive_in_month=1 AND awc.state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY ccs.caste;
-- QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=161714.71..161726.93 rows=4 width=12)
--                      Group Key: ccs.caste
--                      ->  Gather Merge  (cost=161714.71..161726.81 rows=16 width=12)
--                            Workers Planned: 4
--                            ->  Partial GroupAggregate  (cost=160714.65..160724.85 rows=4 width=12)
--                                  Group Key: ccs.caste
--                                  ->  Sort  (cost=160714.65..160718.04 rows=1354 width=4)
--                                        Sort Key: ccs.caste
--                                        ->  Nested Loop  (cost=1.10..160644.22 rows=1354 width=4)
--                                              ->  Parallel Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs  (cost=0.56..143525.91 rows=7873 width=37)
--                                                    Index Cond: (month = '2020-05-01'::date)
--                                                    Filter: ((lactating_all = 1) AND (valid_in_month = 1) AND (alive_in_month = 1))
--                                              ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..2.16 rows=1 width=31)
--                                                    Index Cond: (doc_id = ccs.awc_id)
--                                                    Filter: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)
