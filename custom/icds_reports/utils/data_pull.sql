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
    awc.state_name,
    awc.supervisor_name
    t.total_awcs,
    t.visited_awcs,
    CASE
        WHEN t.total_awcs > t.visited_awcs THEN 'NO'
        ELSE 'YES'
    END as all_visited
    FROM "awc_locations" awc LEFT JOIN (
        SELECT
            awc.supervisor_id,
            SUM(awc.num_launched_awcs) as total_awcs,
            ucr.unique_visits as visited_awcs
            FROM "agg_awc" awc LEFT JOIN "temp_visit_table" ucr
            ON awc.supervisor_id = ucr.supervisor_id
            WHERE awc.aggregation_level = 4 AND month='2020-03-01';
    ) t ON awc.supervisor_id = t.
    WHERE awc.aggregation_level = 4;
