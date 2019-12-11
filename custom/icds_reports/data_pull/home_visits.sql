/*
District
Block
Sector
AWC
Number of home visits planned as per home visit planner
Number of home visits undertaken
*/

SELECT state_name, district_name, block_name, supervisor_name, awc_name,
expected_visits, valid_visits
FROM "public"."awc_location_months_local" "awc_location_months"
    LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    )
WHERE "agg_awc"."month" = '2019-11-01' AND "agg_awc"."aggregation_level"=5 AND "agg_awc"."state_is_test"=0

/*
Nested Loop  (cost=80296.62..210426.04 rows=6 width=84)
   ->  Gather  (cost=80296.62..210400.98 rows=1 width=88)
         Workers Planned: 4
         ->  Parallel Hash Join  (cost=79296.62..209400.88 rows=1 width=88)
               Hash Cond: ((agg_awc_1.state_id = awc_location.state_id) AND (agg_awc_1.district_id = awc_location.district_id) AND (agg_awc_1.block_id = awc_location.block_id) AND (agg_awc_1.supervisor_id = awc_location.supervisor_id) AND (agg_awc_1.awc_id = awc_location.doc_id))
               ->  Parallel Append  (cost=0.00..112965.44 rows=178272 width=181)
                     ->  Parallel Seq Scan on "agg_awc_2019-11-01_5" agg_awc_1  (cost=0.00..112074.08 rows=178272 width=181)
                           Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5))
                     ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=176)
                           Filter: ((month = '2019-11-01'::date) AND (aggregation_level = 5))
               ->  Parallel Hash  (cost=69540.88..69540.88 rows=178255 width=240)
                     ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..69540.88 rows=178255 width=240)
                           Filter: (aggregation_level = 5)
   ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
         Filter: (start_date = '2019-11-01'::date)
(15 rows)
*/
