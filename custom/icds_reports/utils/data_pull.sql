

SELECT caste, count(*) as number_0_3_child FROM "child_health_monthly" WHERE
    month='2020-05-01'
    AND age_tranche::Integer<=36
    AND valid_in_month=1
    AND state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY caste;
-- QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=75021.83..75123.62 rows=200 width=12)
--                      Group Key: child_health_monthly.caste
--                      ->  Gather Merge  (cost=75021.83..75117.62 rows=800 width=12)
--                            Workers Planned: 4
--                            ->  Sort  (cost=74021.77..74022.27 rows=200 width=12)
--                                  Sort Key: child_health_monthly.caste
--                                  ->  Partial HashAggregate  (cost=74012.13..74014.13 rows=200 width=12)
--                                        Group Key: child_health_monthly.caste
--                                        ->  Parallel Append  (cost=0.00..73930.32 rows=16362 width=4)
--                                              ->  Parallel Seq Scan on "child_health_monthly_2020-05-01_671996" child_health_monthly  (cost=0.00..73848.51 rows=16362 width=4)
--                                                    Filter: ((month = '2020-05-01'::date) AND (valid_in_month = 1) AND (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text) AND ((age_tranche)::integer <= 36))

SELECT caste, count(*) as number_3_6_child FROM "child_health_monthly" WHERE
    month='2020-05-01'
    AND age_tranche::Integer>36 AND age_tranche::Integer<=72
    AND valid_in_month=1
    AND state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY caste;

--                                                                                                                     QUERY PLAN
-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=76594.02..76699.15 rows=200 width=12)
--                      Group Key: child_health_monthly.caste
--                      ->  Gather Merge  (cost=76594.02..76693.15 rows=800 width=12)
--                            Workers Planned: 4
--                            ->  Partial GroupAggregate  (cost=75593.96..75597.80 rows=200 width=12)
--                                  Group Key: child_health_monthly.caste
--                                  ->  Sort  (cost=75593.96..75594.57 rows=246 width=4)
--                                        Sort Key: child_health_monthly.caste
--                                        ->  Parallel Append  (cost=0.00..75584.19 rows=246 width=4)
--                                              ->  Parallel Seq Scan on "child_health_monthly_2020-05-01_671996" child_health_monthly  (cost=0.00..75582.96 rows=246 width=4)
--                                                    Filter: ((month = '2020-05-01'::date) AND (valid_in_month = 1) AND (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text) AND ((age_tranche)::integer > 36) AND ((age_tranche)::integer <= 72))
-- (18 rows)

SELECT ccs.caste, count(*) as number_pw FROM "ccs_record_monthly" ccs
    LEFT JOIN "awc_location" awc ON awc.doc_id = ccs.awc_id
    WHERE ccs.month='2020-05-01' AND ccs.pregnant_all=1 AND awc.state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY ccs.caste;
--                                                                                          QUERY PLAN
-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=162363.88..162375.42 rows=4 width=12)
--                      Group Key: ccs.caste
--                      ->  Gather Merge  (cost=162363.88..162375.28 rows=20 width=12)
--                            Workers Planned: 5
--                            ->  Partial GroupAggregate  (cost=161363.80..161372.79 rows=4 width=12)
--                                  Group Key: ccs.caste
--                                  ->  Sort  (cost=161363.80..161366.78 rows=1193 width=4)
--                                        Sort Key: ccs.caste
--                                        ->  Merge Join  (cost=161008.16..161302.84 rows=1193 width=4)
--                                              Merge Cond: (awc.doc_id = ccs.awc_id)
--                                              ->  Sort  (cost=13399.63..13454.34 rows=21883 width=31)
--                                                    Sort Key: awc.doc_id
--                                                    ->  Parallel Index Only Scan using awc_location_pkey_102840 on awc_location_102840 awc  (cost=0.68..11822.13 rows=21883 width=31)
--                                                          Index Cond: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)
--                                              ->  Sort  (cost=147608.53..147695.21 rows=34672 width=37)
--                                                    Sort Key: ccs.awc_id
--                                                    ->  Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs  (cost=0.56..144438.45 rows=34672 width=37)
--                                                          Index Cond: (month = '2020-05-01'::date)
--                                                          Filter: (pregnant_all = 1)
-- (26 rows)

SELECT ccs.caste, count(*) as number_lm FROM "ccs_record_monthly" ccs
    LEFT JOIN "awc_location" awc ON awc.doc_id = ccs.awc_id
    WHERE ccs.month='2020-05-01' AND ccs.lactating_all=1 AND awc.state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY ccs.caste;
-- QUERY PLAN
-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.caste
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize GroupAggregate  (cost=163898.22..163913.44 rows=4 width=12)
--                      Group Key: ccs.caste
--                      ->  Gather Merge  (cost=163898.22..163913.30 rows=20 width=12)
--                            Workers Planned: 5
--                            ->  Partial GroupAggregate  (cost=162898.14..162910.81 rows=4 width=12)
--                                  Group Key: ccs.caste
--                                  ->  Sort  (cost=162898.14..162902.35 rows=1684 width=4)
--                                        Sort Key: ccs.caste
--                                        ->  Merge Join  (cost=162436.88..162807.90 rows=1684 width=4)
--                                              Merge Cond: (awc.doc_id = ccs.awc_id)
--                                              ->  Sort  (cost=13399.63..13454.34 rows=21883 width=31)
--                                                    Sort Key: awc.doc_id
--                                                    ->  Parallel Index Only Scan using awc_location_pkey_102840 on awc_location_102840 awc  (cost=0.68..11822.13 rows=21883 width=31)
--                                                          Index Cond: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)
--                                              ->  Sort  (cost=149037.25..149159.64 rows=48958 width=37)
--                                                    Sort Key: ccs.awc_id
--                                                    ->  Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs  (cost=0.56..144438.45 rows=48958 width=37)
--                                                          Index Cond: (month = '2020-05-01'::date)
--                                                          Filter: (lactating_all = 1)
-- (26 rows)




SELECT caste, SUM(valid_in_month) as number_0_3_child FROM "agg_child_health_2020-05-01" WHERE
    age_tranche::Integer<=36
    AND state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    AND aggregation_level=5
    GROUP BY caste;

--                                                                                         QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Finalize GroupAggregate  (cost=746196.58..746198.62 rows=4 width=12)
--    Group Key: caste
--    ->  Gather Merge  (cost=746196.58..746198.50 rows=16 width=12)
--          Workers Planned: 4
--          ->  Sort  (cost=745196.52..745196.53 rows=4 width=12)
--                Sort Key: caste
--                ->  Partial HashAggregate  (cost=745196.44..745196.48 rows=4 width=12)
--                      Group Key: caste
--                      ->  Parallel Index Scan using staging_agg_child_health_aggregation_level_state_id_idx14 on "agg_child_health_2020-05-01"  (cost=0.56..743804.61 rows=278367 width=8)
--                            Index Cond: ((aggregation_level = 5) AND (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text))
--                            Filter: ((age_tranche)::integer <= 36)

SELECT caste, SUM(valid_in_month) as number_0_3_child FROM "agg_child_health_2020-05-01" WHERE
    age_tranche::Integer>36 AND age_tranche::Integer<=72
    AND state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    AND aggregation_level=5
    GROUP BY caste;

--                                                                                        QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Finalize GroupAggregate  (cost=751319.07..751352.45 rows=4 width=12)
--    Group Key: caste
--    ->  Gather Merge  (cost=751319.07..751352.33 rows=16 width=12)
--          Workers Planned: 4
--          ->  Partial GroupAggregate  (cost=750319.01..750350.37 rows=4 width=12)
--                Group Key: caste
--                ->  Sort  (cost=750319.01..750329.45 rows=4176 width=8)
--                      Sort Key: caste
--                      ->  Parallel Index Scan using staging_agg_child_health_aggregation_level_state_id_idx14 on "agg_child_health_2020-05-01"  (cost=0.56..750067.87 rows=4176 width=8)
--                            Index Cond: ((aggregation_level = 5) AND (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text))
--                            Filter: (((age_tranche)::integer > 36) AND ((age_tranche)::integer <= 72))
--


SELECT ccs.caste, SUM(ccs.pregnant_all) as number_pw FROM "agg_ccs_record_2020-05-01_5" ccs
    LEFT JOIN "awc_location_local" awc ON awc.doc_id = ccs.awc_id
    WHERE awc.state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY ccs.caste;

-- QUERY PLAN
-- -----------------------------------------------------------------------------------------------------------------------------------------------------------
--  Finalize GroupAggregate  (cost=387991.71..387993.74 rows=4 width=12)
--    Group Key: ccs.caste
--    ->  Gather Merge  (cost=387991.71..387993.62 rows=16 width=12)
--          Workers Planned: 4
--          ->  Sort  (cost=386991.65..386991.66 rows=4 width=12)
--                Sort Key: ccs.caste
--                ->  Partial HashAggregate  (cost=386991.57..386991.61 rows=4 width=12)
--                      Group Key: ccs.caste
--                      ->  Parallel Hash Join  (cost=333549.77..386354.32 rows=127450 width=8)
--                            Hash Cond: (awc.doc_id = ccs.awc_id)
--                            ->  Parallel Index Only Scan using awc_location_local_pkey on awc_location_local awc  (cost=0.68..44581.12 rows=27161 width=31)
--                                  Index Cond: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)
--                            ->  Parallel Hash  (cost=317850.82..317850.82 rows=737382 width=41)
--                                  ->  Parallel Seq Scan on "agg_ccs_record_2020-05-01_5" ccs  (cost=0.00..317850.82 rows=737382 width=41)                                           Index Cond: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)                                                 Filter: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)

SELECT ccs.caste, SUM(ccs.lactating_all) as number_lm FROM "agg_ccs_record_2020-05-01_5" ccs
    LEFT JOIN "awc_location_local" awc ON awc.doc_id = ccs.awc_id
    WHERE awc.state_id='f9b47ea2ee2d8a02acddeeb491d3e175'
    GROUP BY ccs.caste;
-- QUERY PLAN
-- -----------------------------------------------------------------------------------------------------------------------------------------------------------
--  Finalize GroupAggregate  (cost=387991.71..387993.74 rows=4 width=12)
--    Group Key: ccs.caste
--    ->  Gather Merge  (cost=387991.71..387993.62 rows=16 width=12)
--          Workers Planned: 4
--          ->  Sort  (cost=386991.65..386991.66 rows=4 width=12)
--                Sort Key: ccs.caste
--                ->  Partial HashAggregate  (cost=386991.57..386991.61 rows=4 width=12)
--                      Group Key: ccs.caste
--                      ->  Parallel Hash Join  (cost=333549.77..386354.32 rows=127450 width=8)
--                            Hash Cond: (awc.doc_id = ccs.awc_id)
--                            ->  Parallel Index Only Scan using awc_location_local_pkey on awc_location_local awc  (cost=0.68..44581.12 rows=27161 width=31)
--                                  Index Cond: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)
--                            ->  Parallel Hash  (cost=317850.82..317850.82 rows=737382 width=41)
--                                  ->  Parallel Seq Scan on "agg_ccs_record_2020-05-01_5" ccs  (cost=0.00..317850.82 rows=737382 width=41)                                                  Filter: (state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'::text)

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
