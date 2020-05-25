SELECT
    awc_location_local.state_name,
    awc_location_local.district_name,
    valid_visits as valid_visits_Jan,
    expected_visits as expected_visits_Jan
    FROM "agg_awc" INNER JOIN awc_location_local ON (
        "agg_awc".district_id = awc_location_local.district_id and
        "agg_awc".aggregation_level=awc_location_local.aggregation_level
    ) WHERE "agg_awc".month='2020-01-01'
    AND "agg_awc".aggregation_level=2
    AND awc_location_local.district_is_test IS DISTINCT FROM 1
    AND awc_location_local.state_is_test IS DISTINCT FROM 1;

SELECT
    awc_location_local.state_name,
    awc_location_local.district_name,
    valid_visits as valid_visits_Feb,
    expected_visits as expected_visits_Feb
    FROM "agg_awc" INNER JOIN awc_location_local ON (
        "agg_awc".district_id = awc_location_local.district_id and
        "agg_awc".aggregation_level=awc_location_local.aggregation_level
    ) WHERE "agg_awc".month='2020-02-01'
    AND "agg_awc".aggregation_level=2
    AND awc_location_local.district_is_test IS DISTINCT FROM 1
    AND awc_location_local.state_is_test IS DISTINCT FROM 1;

SELECT
    awc_location_local.state_name,
    awc_location_local.district_name,
    valid_visits as valid_visits_Mar,
    expected_visits as expected_visits_Mar
    FROM "agg_awc" INNER JOIN awc_location_local ON (
        "agg_awc".district_id = awc_location_local.district_id and
        "agg_awc".aggregation_level=awc_location_local.aggregation_level
    ) WHERE "agg_awc".month='2020-03-01'
    AND "agg_awc".aggregation_level=2
    AND awc_location_local.district_is_test IS DISTINCT FROM 1
    AND awc_location_local.state_is_test IS DISTINCT FROM 1;
 
 --                                                           QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------
--  Hash Join  (cost=57.44..270.45 rows=398 width=27)
--    Hash Cond: (awc_location_local.district_id = agg_awc.district_id)
--    ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local  (cost=0.42..187.30 rows=422 width=55)
--          Index Cond: (aggregation_level = 2)
--          Filter: ((district_is_test IS DISTINCT FROM 1) AND (state_is_test IS DISTINCT FROM 1))
--    ->  Hash  (cost=52.01..52.01 rows=401 width=45)
--          ->  Append  (cost=0.00..52.01 rows=401 width=45)
--                ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=44)
--                      Filter: ((aggregation_level = 2) AND (month = '2020-01-01'::date))
--                ->  Seq Scan on "agg_awc_2020-01-01_2"  (cost=0.00..50.00 rows=400 width=45)
--                      Filter: ((aggregation_level = 2) AND (month = '2020-01-01'::date))
-- (11 rows)
