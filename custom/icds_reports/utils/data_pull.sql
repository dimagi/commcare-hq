SELECT
    awc_location_local.state_name,
    awc_location_local.district_name,
    valid_visits as valid_visits_Jan,
    expected_visits as expected_visits_Jan
    FROM "agg_awc" INNER JOIN awc_location_local ON (
        "agg_awc".district_id = awc_location_local.district_id and
        "agg_awc".aggregation_level=awc_location_local.aggregation_level
    ) WHERE "agg_awc".month='2020-01-01' AND "agg_awc".aggregation_level=2 AND awc_location_local.district_is_test IS DISTINCT FROM 1;

SELECT
    awc_location_local.state_name,
    awc_location_local.district_name,
    valid_visits as valid_visits_Feb,
    expected_visits as expected_visits_Feb
    FROM "agg_awc" INNER JOIN awc_location_local ON (
        "agg_awc".district_id = awc_location_local.district_id and
        "agg_awc".aggregation_level=awc_location_local.aggregation_level
    ) WHERE "agg_awc".month='2020-02-01' AND "agg_awc".aggregation_level=2 AND awc_location_local.district_is_test IS DISTINCT FROM 1;

SELECT
    awc_location_local.state_name,
    awc_location_local.district_name,
    valid_visits as valid_visits_Mar,
    expected_visits as expected_visits_Mar
    FROM "agg_awc" INNER JOIN awc_location_local ON (
        "agg_awc".district_id = awc_location_local.district_id and
        "agg_awc".aggregation_level=awc_location_local.aggregation_level
    ) WHERE "agg_awc".month='2020-03-01' AND "agg_awc".aggregation_level=2 AND awc_location_local.district_is_test IS DISTINCT FROM 1;
