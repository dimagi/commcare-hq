CREATE TEMPORARY TABLE "temp_visit_table" AS (
    SELECT
        location_id as supervisor_id,
        COUNT (DISTINCT awc_id) as unique_visits
    FROM "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0"
    WHERE
        submitted_on>= '2020-02-01'
        AND submitted_on<'2020-04-01'
        AND location_entered IS NOT NULL
        AND location_entered <> ''
    GROUP BY location_id
);

--                                                                                           QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--    Group Key: remote_scan.supervisor_id
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  GroupAggregate  (cost=1205.95..1235.94 rows=251 width=41)
--                      Group Key: location_id
--                      ->  Sort  (cost=1205.95..1215.11 rows=3664 width=66)
--                            Sort Key: location_id
--                            ->  Seq Scan on "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0_103162" "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0"  (cost=0.00..989.06 rows=3664 width=66)
--                                  Filter: ((location_entered IS NOT NULL) AND (submitted_on >= '2020-02-01'::date) AND (submitted_on < '2020-04-01'::date) AND (location_entered <> ''::text))
-- (13 rows)


SELECT
    t.state_name,
    t.supervisor_name,
    t.supervisor_site_code,
    SUM(awc.num_launched_awcs) as total_awcs,
    ucr.unique_visits as visited_awcs,
    CASE
        WHEN total_awcs > visited_awcs THEN 'NO'
        ELSE 'YES'
    END as all_visited
    FROM "agg_awc_2020-03-01_4" awc
    LEFT JOIN "temp_visit_table" ucr
        ON awc.supervisor_id = ucr.supervisor_id
    LEFT JOIN "awc_location_local" t
        ON (t.supervisor_id = awc.supervisor_id
        AND t.aggregation_level=awc.aggregation_level
        AND t.aggregation_level=4) GROUP BY awc.supervisor_id, t.state_name, t.supervisor_name, t.supervisor_site_code;
 
DROP TABLE IF EXISTS temp_visit_table;

SELECT
    state_name,
    supervisor_name,
    supervisor_id
    FROM "system_usage_report_view"
    WHERE month='2020-03-01' AND aggregation_level=4;
    
    
-- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Merge Left Join  (cost=20453.05..24937.10 rows=27173 width=62)
--    Merge Cond: (awc_location.supervisor_id = agg_awc.supervisor_id)
--    Join Filter: ((months.start_date = agg_awc.month) AND (awc_location.aggregation_level = agg_awc.aggregation_level) AND (awc_location.state_id = agg_awc.state_id) AND (awc_location.district_id = agg_awc.district_id) AND (awc_location.block_id = agg_awc.block_id) AND (awc_location.doc_id = agg_awc.awc_id))
--    ->  Merge Left Join  (cost=20452.61..21194.20 rows=27173 width=198)
--          Merge Cond: ((awc_location.supervisor_id = agg_ls.supervisor_id) AND (awc_location.state_id = agg_ls.state_id) AND (awc_location.district_id = agg_ls.district_id) AND (awc_location.block_id = agg_ls.block_id))
--          Join Filter: ((months.start_date = agg_ls.month) AND (awc_location.aggregation_level = agg_ls.aggregation_level))
--          ->  Sort  (cost=15808.60..15876.53 rows=27173 width=198)
--                Sort Key: awc_location.supervisor_id, awc_location.state_id, awc_location.district_id, awc_location.block_id
--                ->  Nested Loop  (cost=0.42..12282.12 rows=27173 width=198)
--                      ->  Seq Scan on icds_months_local months  (cost=0.00..1.52 rows=1 width=4)
--                            Filter: (start_date = '2020-03-01'::date)
--                      ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..12008.87 rows=27173 width=194)
--                            Index Cond: (aggregation_level = 4)
--          ->  Materialize  (cost=4644.01..4777.98 rows=26794 width=138)
--                ->  Sort  (cost=4644.01..4711.00 rows=26794 width=138)
--                      Sort Key: agg_ls.supervisor_id, agg_ls.state_id, agg_ls.district_id, agg_ls.block_id
--                      ->  Append  (cost=0.00..1545.87 rows=26794 width=138)
--                            ->  Seq Scan on agg_ls  (cost=0.00..0.00 rows=1 width=134)
--                                  Filter: ((month = '2020-03-01'::date) AND (aggregation_level = 4))
--                            ->  Seq Scan on "agg_ls_2020-03-01_4"  (cost=0.00..1411.89 rows=26793 width=138)
--                                  Filter: ((month = '2020-03-01'::date) AND (aggregation_level = 4))
--    ->  Materialize  (cost=0.43..2923.63 rows=26825 width=144)
--          ->  Merge Append  (cost=0.43..2856.57 rows=26825 width=144)
--                Sort Key: agg_awc.supervisor_id
--                ->  Sort  (cost=0.01..0.02 rows=1 width=168)
--                      Sort Key: agg_awc.supervisor_id
--                      ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=168)
--                            Filter: ((month = '2020-03-01'::date) AND (aggregation_level = 4))
--                ->  Index Scan using "agg_awc_2020-03-01_4_supervisor_id_idx" on "agg_awc_2020-03-01_4" agg_awc_1  (cost=0.41..2588.29 rows=26824 width=144)
--                      Filter: ((month = '2020-03-01'::date) AND (aggregation_level = 4))
