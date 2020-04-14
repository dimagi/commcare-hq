SELECT
    awc.awc_name,
    awc.awc_site_code,
    awc.supervisor_name,
    awc.supervisor_site_code,
    awc.block_name,
    awc.block_site_code,
    awc.district_name,
    awc.district_site_code,
    awc.state_name,
    awc.state_site_code,
    ucr.visits
    FROM "awc_location" awc LEFT JOIN (
        SELECT
            awc_id,
            count(*) as visits
        FROM "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0"
        WHERE submitted_on >= '2020-01-01' AND
                  submitted_on < '2020-03-01'
        GROUP BY awc_id
    ) ucr
    ON ucr.awc_id = awc.doc_id
    WHERE awc.aggregation_level=5;
--
--                                                                                         QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    ->  Distributed Subplan 9_1
--          ->  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--                Group Key: remote_scan.awc_id
--                ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--                      Task Count: 64
--                      Tasks Shown: One of 64
--                      ->  Task
--                            Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                            ->  HashAggregate  (cost=973.51..1007.86 rows=3435 width=41)
--                                  Group Key: awc_id
--                                  ->  Seq Scan on "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0_103162" "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0"  (cost=0.00..948.19 rows=5064 width=33)
--                                        Filter: ((submitted_on >= '2020-01-01'::date) AND (submitted_on < '2020-03-01'::date))
--    Task Count: 1
--    Tasks Shown: All
--    ->  Task
--          Node: host=100.71.184.222 port=6432 dbname=icds_ucr
--          ->  Merge Left Join  (cost=60.38..114161.52 rows=734238 width=121)
--                Merge Cond: (awc.doc_id = intermediate_result.awc_id)
--                ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..112248.59 rows=734238 width=144)
--                      Filter: (aggregation_level = 5)
--                ->  Sort  (cost=59.83..62.33 rows=1000 width=40)
--                      Sort Key: intermediate_result.awc_id
--                      ->  Function Scan on read_intermediate_result intermediate_result  (cost=0.00..10.00 rows=1000 width=40)
-- (24 rows)

