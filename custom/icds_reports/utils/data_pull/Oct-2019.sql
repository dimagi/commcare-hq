/*
# Total AWCs
# AWCs Launched
# Districts launched
# Avg. # of Days AWCs open
*/
SELECT
state_name,
num_awcs,
num_launched_awcs,
num_launched_districts,
awc_days_open,
CASE WHEN num_launched_awcs>0 THEN awc_days_open/num_launched_awcs ELSE awc_days_open END AS average_awc_open
FROM agg_awc_monthly WHERE aggregation_level=1 AND month='2019-10-01'


-- # of AWCs that submitted Infra form
SELECT state_name, sum(num_awc_infra_last_update)
FROM agg_awc_monthly
WHERE aggregation_level=1 AND month='2019-10-01'
GROUP BY state_name

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
FROM "public"."awc_location_months_local" "awc_location_months" LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    )
WHERE "agg_awc"."aggregation_level"=5 AND "agg_awc"."month"='2019-10-01' AND awc_is_test<>1 AND supervisor_is_test<>1 AND block_is_test<>1 AND district_is_test<>1
GROUP BY state_name

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
WHERE "agg_awc"."aggregation_level"=5 AND "agg_awc"."month"='2019-10-01' AND awc_is_test<>1 AND supervisor_is_test<>1 AND block_is_test<>1 AND district_is_test<>1
GROUP BY state_name


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
FROM "public"."awc_location_months_local" "awc_location_months" LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    )
WHERE "agg_awc"."aggregation_level"=5 AND "agg_awc"."month"='2019-10-01' AND awc_is_test<>1 AND supervisor_is_test<>1 AND block_is_test<>1 AND district_is_test<>1
GROUP BY state_name


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
WHERE "agg_awc"."aggregation_level"=5 AND "agg_awc"."month"='2019-10-01' AND awc_is_test<>1 AND supervisor_is_test<>1 AND block_is_test<>1 AND district_is_test<>1
GROUP BY state_name


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


-- # Children (0-6y)
SELECT state_name,
Count(*) FILTER (WHERE age_tranche::integer<=72 OR age_tranche IS null) AS "0-6y"
FROM agg_child_health_monthly
WHERE aggregation_level=1 AND month='2019-10-01'
GROUP BY state_name
