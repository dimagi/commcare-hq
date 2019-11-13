/*
# Total AWCs
# AWCs Launched
# Districts launched
# Avg. # of Days AWCs open
*/
-- Approach 1: Use view agg_awc_monthly
SELECT
state_name,
num_awcs,
num_launched_awcs,
num_launched_districts,
awc_days_open,
CASE WHEN num_launched_awcs>0 THEN awc_days_open/num_launched_awcs ELSE awc_days_open END AS average_awc_open
FROM agg_awc_monthly WHERE aggregation_level=1 AND month='2019-10-01'

/*
 Hash Left Join  (cost=3.00..51.50 rows=198 width=30)
   Hash Cond: ((months.start_date = agg_awc.month) AND (awc_location.aggregation_level = agg_awc.aggregation_level) AND (awc_location.state_id = agg_awc.state_id) AND (awc_location.district_id = agg_awc.district_id) AND (awc_location.block_id = agg_awc.block_id) AND (awc_location.supervisor_id = agg_awc.supervisor_id) AND (awc_location.doc_id = agg_awc.awc_id))
   ->  Nested Loop  (cost=0.42..42.73 rows=198 width=178)
         ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..15.24 rows=33 width=174)
               Index Cond: (aggregation_level = 1)
         ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
               ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                     Filter: (start_date = '2019-10-01'::date)
   ->  Hash  (cost=2.52..2.52 rows=2 width=184)
         ->  Append  (cost=0.00..2.52 rows=2 width=184)
               ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=184)
                     Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
               ->  Seq Scan on "agg_awc_2019-10-01_1" agg_awc_1  (cost=0.00..2.51 rows=1 width=184)
                     Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(14 rows)
*/

-- Approach 2: Use agg_awc instead and join with awc_location
SELECT
    state_name,
    num_awcs,
    num_launched_awcs,
    num_launched_districts,
    awc_days_open,
    CASE WHEN num_launched_awcs>0 THEN awc_days_open/num_launched_awcs ELSE awc_days_open END AS average_awc_open
FROM
    (SELECT * FROM agg_awc WHERE aggregation_level=1 AND month='2019-10-01') result
    RIGHT JOIN "public"."awc_location_local" "awc_location" ON (
        ("awc_location"."aggregation_level" = result."aggregation_level") AND
        ("awc_location"."state_id" = result."state_id")
    )

/*
 Hash Left Join  (cost=2.55..80295.82 rows=713334 width=30)
   Hash Cond: ((awc_location.aggregation_level = agg_awc.aggregation_level) AND (awc_location.state_id = agg_awc.state_id))
   ->  Seq Scan on awc_location_local awc_location  (cost=0.00..71297.34 rows=713334 width=47)
   ->  Hash  (cost=2.52..2.52 rows=2 width=52)
         ->  Append  (cost=0.00..2.52 rows=2 width=52)
               ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=52)
                     Filter: ((aggregation_level = 1) AND (month = '2019-10-01'::date))
               ->  Seq Scan on "agg_awc_2019-10-01_1"  (cost=0.00..2.51 rows=1 width=52)
                     Filter: ((aggregation_level = 1) AND (month = '2019-10-01'::date))
(9 rows)
*/

-- # of AWCs that submitted Infra form
-- Approach 1: Use view agg_awc_monthly
SELECT state_name, sum(num_awc_infra_last_update)
FROM agg_awc_monthly
WHERE aggregation_level=1 AND month='2019-10-01'
GROUP BY state_name

/*
 HashAggregate  (cost=51.50..51.72 rows=22 width=18)
   Group Key: awc_location.state_name
   ->  Hash Left Join  (cost=3.00..50.51 rows=198 width=14)
         Hash Cond: ((months.start_date = agg_awc.month) AND (awc_location.aggregation_level = agg_awc.aggregation_level) AND (awc_location.state_id = agg_awc.state_id) AND (awc_location.district_id = agg_awc.district_id) AND (awc_location.block_id = agg_awc.block_id) AND (awc_location.supervisor_id = agg_awc.supervisor_id) AND (awc_location.doc_id = agg_awc.awc_id))
         ->  Nested Loop  (cost=0.42..42.73 rows=198 width=178)
               ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..15.24 rows=33 width=174)
                     Index Cond: (aggregation_level = 1)
               ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-10-01'::date)
         ->  Hash  (cost=2.52..2.52 rows=2 width=172)
               ->  Append  (cost=0.00..2.52 rows=2 width=172)
                     ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=172)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                     ->  Seq Scan on "agg_awc_2019-10-01_1" agg_awc_1  (cost=0.00..2.51 rows=1 width=172)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(16 rows)
*/

-- Approach 2: Use agg_awc instead and join with awc_location
SELECT state_name, total_that_did_awc_infra_last_update
FROM
    (SELECT
        aggregation_level, state_id,
        sum(num_awc_infra_last_update) AS total_that_did_awc_infra_last_update
        FROM agg_awc
        WHERE aggregation_level=1 AND month='2019-10-01'
        GROUP BY state_id, aggregation_level
    ) RESULT
    RIGHT JOIN "public"."awc_location_local" "awc_location" ON (
        ("awc_location"."state_id" = result."state_id") AND
        ("awc_location"."aggregation_level" = result."aggregation_level")
    )
/*
--------------------------------------------------------------------------------------------------------------------------
 Hash Left Join  (cost=2.62..75093.51 rows=713334 width=18)
   Hash Cond: ((awc_location.state_id = result.state_id) AND (awc_location.aggregation_level = result.aggregation_level))
   ->  Seq Scan on awc_location_local awc_location  (cost=0.00..71297.34 rows=713334 width=47)
   ->  Hash  (cost=2.59..2.59 rows=2 width=44)
         ->  Subquery Scan on result  (cost=2.53..2.59 rows=2 width=44)
               ->  GroupAggregate  (cost=2.53..2.57 rows=2 width=44)
                     Group Key: agg_awc.state_id, agg_awc.aggregation_level
                     ->  Sort  (cost=2.53..2.53 rows=2 width=40)
                           Sort Key: agg_awc.state_id
                           ->  Append  (cost=0.00..2.52 rows=2 width=40)
                                 ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=40)
                                       Filter: ((aggregation_level = 1) AND (month = '2019-10-01'::date))
                                 ->  Seq Scan on "agg_awc_2019-10-01_1"  (cost=0.00..2.51 rows=1 width=40)
                                       Filter: ((aggregation_level = 1) AND (month = '2019-10-01'::date))
(14 rows)
*/

-- Approach 3: Join first, filter later
SELECT state_name, sum(num_awc_infra_last_update)
FROM agg_awc awc
right join awc_location_local loc
on loc.aggregation_level=awc.aggregation_level and loc.state_id=awc.state_id
WHERE awc.aggregation_level=1 AND month='2019-10-01'
GROUP BY state_name;

/*
 GroupAggregate  (cost=17.93..17.97 rows=2 width=18)
   Group Key: loc.state_name
   ->  Sort  (cost=17.93..17.94 rows=2 width=14)
         Sort Key: loc.state_name
         ->  Hash Join  (cost=2.97..17.92 rows=2 width=14)
               Hash Cond: (loc.state_id = awc.state_id)
               ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local loc  (cost=0.42..15.24 rows=33 width=47)
                     Index Cond: (aggregation_level = 1)
               ->  Hash  (cost=2.52..2.52 rows=2 width=40)
                     ->  Append  (cost=0.00..2.52 rows=2 width=40)
                           ->  Seq Scan on agg_awc awc  (cost=0.00..0.00 rows=1 width=40)
                                 Filter: ((aggregation_level = 1) AND (month = '2019-10-01'::date))
                           ->  Seq Scan on "agg_awc_2019-10-01_1" awc_1  (cost=0.00..2.51 rows=1 width=40)
                                 Filter: ((aggregation_level = 1) AND (month = '2019-10-01'::date))
(14 rows)
*/

/*
# of AWCs that reported available drinking water
# of AWCs that reported unavailable drinking water
# of AWCs that reported available functional toilet
# of AWCs that reported unavailable functional toilet
*/
SELECT state_name,
count(*) FILTER (WHERE infra_clean_water=1) AS "Available drinking water",
count(*) FILTER (WHERE infra_clean_water=0) AS "Unavailable drinking water",
count(*) FILTER (WHERE infra_functional_toilet=1) AS "Available functional toilet",
count(*) FILTER (WHERE infra_functional_toilet=0) AS "Unavailable functional toilet"
FROM agg_awc_monthly
WHERE aggregation_level=5 AND month='2019-10-01'
GROUP BY state_name

/*
 GroupAggregate  (cost=269160.09..269160.30 rows=6 width=42)
   Group Key: awc_location.state_name
   ->  Sort  (cost=269160.09..269160.10 rows=6 width=18)
         Sort Key: awc_location.state_name
         ->  Nested Loop  (cost=1000.00..269160.01 rows=6 width=18)
               ->  Gather  (cost=1000.00..269134.95 rows=1 width=22)
                     Workers Planned: 4
                     ->  Nested Loop  (cost=0.00..268134.85 rows=1 width=22)
                           ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..66393.17 rows=171058 width=174)
                                 Filter: (aggregation_level = 5)
                           ->  Append  (cost=0.00..1.16 rows=2 width=181)
                                 ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=176)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id) AND (awc_location.doc_id = awc_id))
                                 ->  Index Scan using "agg_awc_2019-10-01_5_awc_id_idx" on "agg_awc_2019-10-01_5" agg_awc_1  (cost=0.55..1.15 rows=1 width=181)
                                       Index Cond: (awc_id = awc_location.doc_id)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id))
               ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                     Filter: (start_date = '2019-10-01'::date)
(18 rows)
*/

-- just use agg_awc instead of using the view, it however appears to be more costly

SELECT state_id,
count(*) FILTER (WHERE infra_clean_water=1) AS "Available drinking water",
count(*) FILTER (WHERE infra_clean_water=0) AS "Unavailable drinking water",
count(*) FILTER (WHERE infra_functional_toilet=1) AS "Available functional toilet",
count(*) FILTER (WHERE infra_functional_toilet=0) AS "Unavailable functional toilet"
FROM agg_awc
WHERE aggregation_level=5 AND month='2019-10-01'
GROUP BY state_id

/*
 Finalize GroupAggregate  (cost=308600.43..308708.21 rows=200 width=65)
   Group Key: "agg_awc_2019-10-01_5".state_id
   ->  Gather Merge  (cost=308600.43..308696.21 rows=800 width=65)
         Workers Planned: 4
         ->  Sort  (cost=307600.37..307600.87 rows=200 width=65)
               Sort Key: "agg_awc_2019-10-01_5".state_id
               ->  Partial HashAggregate  (cost=307590.72..307592.72 rows=200 width=65)
                     Group Key: "agg_awc_2019-10-01_5".state_id
                     ->  Parallel Append  (cost=0.00..303739.40 rows=171170 width=41)
                           ->  Parallel Seq Scan on "agg_awc_2019-10-01_5"  (cost=0.00..302883.55 rows=171170 width=41)
                                 Filter: ((aggregation_level = 5) AND (month = '2019-10-01'::date))
                           ->  Parallel Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=40)
                                 Filter: ((aggregation_level = 5) AND (month = '2019-10-01'::date))
(13 rows)
*/

/*
# of AWCs that reported usable infantometer
# of AWCs that reported unavailable usable infantometer
# of AWCs that reported usable stadiometer
# of AWCs that reported unavailable usable stadiometer
*/
SELECT state_name,
count(*) FILTER (WHERE infantometer=1) AS "AWCs that reported usable infantometer",
count(*) FILTER (WHERE infantometer=0) AS "AWCs that reported unavailable usable infantometer",
count(*) FILTER (WHERE stadiometer=1) AS "AWCs that reported usable stadiometer",
count(*) FILTER (WHERE stadiometer=0) AS "AWCs that reported unavailable usable stadiometer"
FROM "public"."awc_location_months_local" "awc_location_months" LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    )
WHERE "agg_awc"."aggregation_level"=5 AND "agg_awc"."month"='2019-10-01'
GROUP BY state_name

/*
GroupAggregate  (cost=269160.09..269160.30 rows=6 width=42)
   Group Key: awc_location.state_name
   ->  Sort  (cost=269160.09..269160.10 rows=6 width=18)
         Sort Key: awc_location.state_name
         ->  Nested Loop  (cost=1000.00..269160.01 rows=6 width=18)
               ->  Gather  (cost=1000.00..269134.95 rows=1 width=22)
                     Workers Planned: 4
                     ->  Nested Loop  (cost=0.00..268134.85 rows=1 width=22)
                           ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..66393.17 rows=171058 width=174)
                                 Filter: (aggregation_level = 5)
                           ->  Append  (cost=0.00..1.16 rows=2 width=181)
                                 ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=176)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id) AND (awc_location.doc_id = awc_id))
                                 ->  Index Scan using "agg_awc_2019-10-01_5_awc_id_idx" on "agg_awc_2019-10-01_5" agg_awc_1  (cost=0.55..1.15 rows=1 width=181)
                                       Index Cond: (awc_id = awc_location.doc_id)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id))
               ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                     Filter: (start_date = '2019-10-01'::date)
*/


/*
# of AWCs that reported available medicine kit
# of AWCs that reported unavailable medicine kit
# of AWCs that reported available infant weighing scale
# of AWCs that reported unavailable infant weighing scale
# of AWCs that reported available mother and child weighing scale
# of AWCs that reported unavailable mother and child weighing scale
*/
SELECT state_name,
count(*) FILTER (WHERE infra_medicine_kits=1) AS "Available medicine kit",
count(*) FILTER (WHERE infra_medicine_kits=0) AS "Unavailable medicine kit",
count(*) FILTER (WHERE infra_infant_weighing_scale=1) AS "Available infant weighing scale",
count(*) FILTER (WHERE infra_infant_weighing_scale=0) AS "Unavailable infant weighing scale",
count(*) FILTER (WHERE infra_adult_weighing_scale=1) AS "Available mother and child weighing scale",
count(*) FILTER (WHERE infra_adult_weighing_scale=0) AS "Unavailable mother and child weighing scale"
FROM agg_awc_monthly
WHERE aggregation_level=5 AND month='2019-10-01'
GROUP BY state_name

/*
 GroupAggregate  (cost=269160.09..269160.36 rows=6 width=58)
   Group Key: awc_location.state_name
   ->  Sort  (cost=269160.09..269160.10 rows=6 width=22)
         Sort Key: awc_location.state_name
         ->  Nested Loop  (cost=1000.00..269160.01 rows=6 width=22)
               ->  Gather  (cost=1000.00..269134.95 rows=1 width=26)
                     Workers Planned: 4
                     ->  Nested Loop  (cost=0.00..268134.85 rows=1 width=26)
                           ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..66393.17 rows=171058 width=174)
                                 Filter: (aggregation_level = 5)
                           ->  Append  (cost=0.00..1.16 rows=2 width=185)
                                 ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=180)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id) AND (awc_location.doc_id = awc_id))
                                 ->  Index Scan using "agg_awc_2019-10-01_5_awc_id_idx" on "agg_awc_2019-10-01_5" agg_awc_1  (cost=0.55..1.15 rows=1 width=185)
                                       Index Cond: (awc_id = awc_location.doc_id)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id))
               ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                     Filter: (start_date = '2019-10-01'::date)
(18 rows)
*/

/*
# of AWCs that reported available electricity line
# of AWCs that reported unavailable electricity line
# AWCs conducted at least 2 CBE events
*/
SELECT state_name,
count(*) FILTER (WHERE electricity_awc=1) AS "Available electricity line",
count(*) FILTER (WHERE electricity_awc=0) AS "Unavailable electricity line",
sum(num_awcs_conducted_cbe) AS "AWCs conducted at least 2 CBE events",
sum(num_awcs_conducted_vhnd) AS "AWCs conducted at least 1 VHNSD"
FROM "public"."awc_location_months_local" "awc_location_months" LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    )
WHERE "agg_awc"."aggregation_level"=5 AND "agg_awc"."month"='2019-10-01'
GROUP BY state_name

/*
GroupAggregate  (cost=269160.09..269160.27 rows=6 width=42)
   Group Key: awc_location.state_name
   ->  Sort  (cost=269160.09..269160.10 rows=6 width=22)
         Sort Key: awc_location.state_name
         ->  Nested Loop  (cost=1000.00..269160.01 rows=6 width=22)
               ->  Gather  (cost=1000.00..269134.95 rows=1 width=26)
                     Workers Planned: 4
                     ->  Nested Loop  (cost=0.00..268134.85 rows=1 width=26)
                           ->  Parallel Seq Scan on awc_location_local awc_location  (cost=0.00..66393.17 rows=171058 width=174)
                                 Filter: (aggregation_level = 5)
                           ->  Append  (cost=0.00..1.16 rows=2 width=185)
                                 ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=180)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id) AND (awc_location.doc_id = awc_id))
                                 ->  Index Scan using "agg_awc_2019-10-01_5_awc_id_idx" on "agg_awc_2019-10-01_5" agg_awc_1  (cost=0.55..1.15 rows=1 width=185)
                                       Index Cond: (awc_id = awc_location.doc_id)
                                       Filter: ((awc_is_test <> 1) AND (supervisor_is_test <> 1) AND (block_is_test <> 1) AND (district_is_test <> 1) AND (month = '2019-10-01'::date) AND (aggregation_level = 5) AND (awc_location.state_id = state_id) AND (awc_location.district_id = district_id) AND (awc_location.block_id = block_id) AND (awc_location.supervisor_id = supervisor_id))
               ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                     Filter: (start_date = '2019-10-01'::date)
(18 rows)
*/

/*
# Households Registered
# Pregnant Women (should this use cases_ccs_pregnant or cases_ccs_pregnant_all)
# Lactating Mothers (cases_ccs_lactating or cases_ccs_lactating_all)
# Adolescent Girls (11-14y)
*/
SELECT state_name,
SUM(cases_household) AS "Open Household Cases",
SUM(cases_ccs_pregnant) AS "Pregnant",
SUM(cases_ccs_lactating) AS "Lactating",
Sum(cases_person_adolescent_girls_11_14) AS "Adolescent Girls (11-14y)"
FROM agg_awc_monthly
WHERE aggregation_level=1 AND month='2019-10-01'
GROUP BY state_name

/*
 HashAggregate  (cost=52.98..53.20 rows=22 width=42)
   Group Key: awc_location.state_name
   ->  Hash Left Join  (cost=3.00..50.51 rows=198 width=26)
         Hash Cond: ((months.start_date = agg_awc.month) AND (awc_location.aggregation_level = agg_awc.aggregation_level) AND (awc_location.state_id = agg_awc.state_id) AND (awc_location.district_id = agg_awc.district_id) AND (awc_location.block_id = agg_awc.block_id) AND (awc_location.supervisor_id = agg_awc.supervisor_id) AND (awc_location.doc_id = agg_awc.awc_id))
         ->  Nested Loop  (cost=0.42..42.73 rows=198 width=178)
               ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..15.24 rows=33 width=174)
                     Index Cond: (aggregation_level = 1)
               ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-10-01'::date)
         ->  Hash  (cost=2.52..2.52 rows=2 width=184)
               ->  Append  (cost=0.00..2.52 rows=2 width=184)
                     ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=184)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                     ->  Seq Scan on "agg_awc_2019-10-01_1" agg_awc_1  (cost=0.00..2.51 rows=1 width=184)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(16 rows)
*/

-- # Children (0-6y)
SELECT state_name,
SUM(cases_child_health) AS "0-6y"
FROM agg_awc_monthly
WHERE aggregation_level=1 AND month='2019-10-01'
GROUP BY state_name

/*
 HashAggregate  (cost=51.50..51.72 rows=22 width=18)
   Group Key: awc_location.state_name
   ->  Hash Left Join  (cost=3.00..50.51 rows=198 width=14)
         Hash Cond: ((months.start_date = agg_awc.month) AND (awc_location.aggregation_level = agg_awc.aggregation_level) AND (awc_location.state_id = agg_awc.state_id) AND (awc_location.district_id = agg_awc.district_id) AND (awc_location.block_id = agg_awc.block_id) AND (awc_location.supervisor_id = agg_awc.supervisor_id) AND (awc_location.doc_id = agg_awc.awc_id))
         ->  Nested Loop  (cost=0.42..42.73 rows=198 width=178)
               ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..15.24 rows=33 width=174)
                     Index Cond: (aggregation_level = 1)
               ->  Materialize  (cost=0.00..25.03 rows=6 width=4)
                     ->  Seq Scan on icds_months_local months  (cost=0.00..25.00 rows=6 width=4)
                           Filter: (start_date = '2019-10-01'::date)
         ->  Hash  (cost=2.52..2.52 rows=2 width=172)
               ->  Append  (cost=0.00..2.52 rows=2 width=172)
                     ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=172)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
                     ->  Seq Scan on "agg_awc_2019-10-01_1" agg_awc_1  (cost=0.00..2.51 rows=1 width=172)
                           Filter: ((month = '2019-10-01'::date) AND (aggregation_level = 1))
(16 rows)
*/
