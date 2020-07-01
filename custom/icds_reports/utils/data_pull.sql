CREATE TABLE "temp_visit_table_2_months" AS (
    SELECT
        location_id as supervisor_id,
        COUNT (DISTINCT awc_id) as unique_visits_2_months
    FROM "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0"
    WHERE
        submitted_on>= '2020-05-01'
        AND submitted_on<'2020-07-01'
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

CREATE TABLE "temp_visit_table_may" AS (
    SELECT
        location_id as supervisor_id,
        COUNT (DISTINCT awc_id) as unique_visits_may_month
    FROM "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0"
    WHERE
        submitted_on>= '2020-05-01'
        AND submitted_on<'2020-06-01'
        AND location_entered IS NOT NULL
        AND location_entered <> ''
    GROUP BY location_id
);

CREATE TABLE "temp_visit_table_june" AS (
    SELECT
        location_id as supervisor_id,
        COUNT (DISTINCT awc_id) as unique_visits_june_month
    FROM "ucr_icds-cas_static-awc_mgt_forms_ad1b11f0"
    WHERE
        submitted_on>= '2020-06-01'
        AND submitted_on<'2020-07-01'
        AND location_entered IS NOT NULL
        AND location_entered <> ''
    GROUP BY location_id
);



COPY(SELECT
    t.state_name,
    t.supervisor_name,
    t.supervisor_site_code,
    CASE WHEN al.num_supervisor_launched>0 THEN 'Launched' ELSE 'UnLaunched' END as supervisor_launched_status,
    awc.num_awcs as total_awcs,
    ucr.unique_visits_2_months as visited_awcs,
    ucr_may.unique_visits_may_month as visited_awcs_may,
    ucr_june.unique_visits_june_month as visited_awcs_june,
    CASE
        WHEN awc.num_awcs = ucr.unique_visits THEN 'YES'
        ELSE 'NO'
    END as all_visited
    FROM "agg_ls" al
    LEFT JOIN "temp_visit_table_2_months" ucr
        ON al.supervisor_id = ucr.supervisor_id
    LEFT JOIN "temp_visit_table_may" ucr_may
        ON al.supervisor_id = ucr_may.supervisor_id
    LEFT JOIN "temp_visit_table_june" ucr_june
        ON al.supervisor_id = ucr_june.supervisor_id
    LEFT JOIN "awc_location_local" t
        ON (t.supervisor_id = al.supervisor_id
        AND t.aggregation_level=al.aggregation_level
        AND t.aggregation_level=4)
    LEFT JOIN "agg_awc_2020-06-01_4" awc
        ON (
            awc.supervisor_id = al.supervisor_id
            AND al.aggregation_level=awc.aggregation_level AND awc.aggregation_level=4 AND awc.month='2020-06-01')
    WHERE t.state_is_test<>1 AND t.supervisor_is_test<>1 AND al.aggregation_level=4 AND al.month='2020-06-01') TO '/tmp/ls_data_pull_june.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
-- QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------------
--  Hash Right Join  (cost=7269.36..19669.66 rows=26789 width=115)
--    Hash Cond: ((t.supervisor_id = awc.supervisor_id) AND (t.aggregation_level = awc.aggregation_level))
--    ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local t  (cost=0.42..11122.73 rows=26517 width=75)
--          Index Cond: (aggregation_level = 4)
--    ->  Hash  (cost=6605.10..6605.10 rows=26789 width=53)
--          ->  Hash Right Join  (cost=4172.94..6605.10 rows=26789 width=53)
--                Hash Cond: ((al.supervisor_id = awc.supervisor_id) AND (al.aggregation_level = awc.aggregation_level))
--                ->  Append  (cost=0.00..1547.87 rows=26794 width=39)
--                      ->  Seq Scan on agg_ls al  (cost=0.00..0.00 rows=1 width=38)
--                            Filter: ((aggregation_level = 4) AND (month = '2020-04-01'::date))
--                      ->  Seq Scan on "agg_ls_2020-04-01_4" al_1  (cost=0.00..1413.89 rows=26793 width=39)
--                            Filter: ((aggregation_level = 4) AND (month = '2020-04-01'::date))
--                ->  Hash  (cost=3509.11..3509.11 rows=26789 width=49)
--                      ->  Hash Right Join  (cost=2626.24..3509.11 rows=26789 width=49)
--                            Hash Cond: (ucr.supervisor_id = awc.supervisor_id)
--                            ->  Seq Scan on temp_visit_table ucr  (cost=0.00..248.60 rows=13560 width=40)
--                            ->  Hash  (cost=2055.38..2055.38 rows=26789 width=41)
--                                  ->  Seq Scan on "agg_awc_2020-04-01_4" awc  (cost=0.00..2055.38 rows=26789 width=41)
--                                        Filter: ((state_is_test <> 1) AND (supervisor_is_test <> 1))
 
DROP TABLE IF EXISTS temp_visit_table;
