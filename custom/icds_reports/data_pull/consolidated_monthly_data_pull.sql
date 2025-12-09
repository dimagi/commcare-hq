-- # Total AWCs
-- # AWCs Launched
-- # Districts launched
-- # Avg. # of Days AWCs open
COPY(
SELECT state_name,
num_awcs AS "Total AWCs",
num_launched_awcs AS "AWCs Launched",
num_launched_districts AS "Districts launched",
awc_days_open,
CASE WHEN num_launched_awcs>0 THEN awc_days_open/num_launched_awcs ELSE awc_days_open END AS "Avg. # of Days AWCs open"
FROM agg_awc_monthly
WHERE aggregation_level=1 AND month='2019-12-01'
ORDER BY state_name
) TO '/tmp/monthly_stats1.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

-- # of AWCs that submitted Infra form
-- # Households Registered
-- # Pregnant Women (should this use cases_ccs_pregnant or cases_ccs_pregnant_all)
-- # Lactating Mothers (cases_ccs_lactating or cases_ccs_lactating_all)
-- # Adolescent Girls (11-14y)
-- # Children (0-6y)
COPY(
SELECT state_name,
sum(num_awc_infra_last_update) AS "# of AWCs that submitted Infra form",
SUM(cases_household) AS "# Households Registered",
SUM(cases_ccs_pregnant) AS "# Pregnant Women",
SUM(cases_ccs_lactating) AS "# Lactating Mothers",
SUM(cases_person_adolescent_girls_11_14) AS "# Adolescent Girls (11-14y)",
SUM(cases_child_health) AS "# Children (0-6y)"
FROM agg_awc_monthly
WHERE aggregation_level=1 AND month='2019-12-01'
GROUP BY state_name
ORDER BY state_name
) TO '/tmp/monthly_stats2.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

----Can above two be combined as? ----
COPY(
SELECT state_name,
sum(num_awcs) AS "Total AWCs",
sum(num_launched_awcs) AS "AWCs Launched",
sum(num_launched_districts) AS "Districts launched",
sum(awc_days_open),
CASE WHEN num_launched_awcs>0 THEN awc_days_open/num_launched_awcs ELSE awc_days_open END AS "Avg. # of Days AWCs open",
sum(num_awc_infra_last_update) AS "# of AWCs that submitted Infra form",
SUM(cases_household) AS "# Households Registered",
SUM(cases_ccs_pregnant) AS "# Pregnant Women",
SUM(cases_ccs_lactating) AS "# Lactating Mothers",
SUM(cases_person_adolescent_girls_11_14) AS "# Adolescent Girls (11-14y)",
SUM(cases_child_health) AS "# Children (0-6y)"
FROM agg_awc_monthly
WHERE aggregation_level=1 AND month='2019-12-01'
ORDER BY state_name
) TO '/tmp/monthly_stats1.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


-- # of AWCs that reported available drinking water
-- # of AWCs that reported unavailable drinking water
-- # of AWCs that reported available functional toilet
-- # of AWCs that reported unavailable functional toilet
-- # of AWCs that reported usable infantometer
-- # of AWCs that reported unavailable usable infantometer
-- # of AWCs that reported usable stadiometer
-- # of AWCs that reported unavailable usable stadiometer
-- # of AWCs that reported available medicine kit
-- # of AWCs that reported unavailable medicine kit
-- # of AWCs that reported available infant weighing scale
-- # of AWCs that reported unavailable infant weighing scale
-- # of AWCs that reported available mother and child weighing scale
-- # of AWCs that reported unavailable mother and child weighing scale
COPY(
SELECT state_name,
count(*) FILTER (WHERE infra_clean_water=1) AS "# of AWCs that reported available drinking water",
count(*) FILTER (WHERE infra_clean_water IS NULL OR infra_clean_water=0) AS "# of AWCs that reported unavailable drinking water or did not answer the question",
count(*) FILTER (WHERE infra_functional_toilet=1) AS "# of AWCs that reported available functional toilet",
count(*) FILTER (WHERE infra_functional_toilet IS NULL OR infra_functional_toilet=0) AS "# of AWCs that reported unavailable functional toilet or did not answer the question",
count(*) FILTER (WHERE infantometer=1) AS "# of AWCs that reported usable infantometer",
count(*) FILTER (WHERE infantometer IS NULL OR infantometer=0) AS "# of AWCs that reported unavailable usable infantometer or did not answer the question",
count(*) FILTER (WHERE stadiometer=1) AS "# of AWCs that reported usable stadiometer",
count(*) FILTER (WHERE stadiometer IS NULL OR stadiometer=0) AS "# of AWCs that reported unavailable usable stadiometer or did not answer the question",
count(*) FILTER (WHERE infra_medicine_kits=1) AS "# of AWCs that reported available medicine kit",
count(*) FILTER (WHERE infra_medicine_kits IS NULL OR infra_medicine_kits=0) AS "# of AWCs that reported unavailable medicine kit or did not answer the question",
count(*) FILTER (WHERE infra_infant_weighing_scale=1) AS "# of AWCs that reported available infant weighing scale",
count(*) FILTER (WHERE infra_infant_weighing_scale IS NULL OR infra_infant_weighing_scale=0) AS "# of AWCs that reported unavailable infant weighing scale or did not answer the question",
count(*) FILTER (WHERE infra_adult_weighing_scale=1) AS "# of AWCs that reported available mother and child weighing scale",
count(*) FILTER (WHERE infra_adult_weighing_scale IS NULL OR infra_adult_weighing_scale=0) AS "# of AWCs that reported unavailable mother and child weighing scale or did not answer the question"
FROM agg_awc_monthly
WHERE aggregation_level=5 AND month='2019-12-01'
GROUP BY state_name
ORDER BY state_name
) TO '/tmp/monthly_stats3.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

-- # of AWCs that reported available electricity line
-- # of AWCs that reported unavailable electricity line
-- # AWCs conducted at least 2 CBE events
-- # AWCs conducted at least 1 VHND
COPY(
SELECT state_name,
count(*) FILTER (WHERE electricity_awc=1) AS "# of AWCs that reported available electricity line",
count(*) FILTER (WHERE electricity_awc IS NULL OR electricity_awc=0) AS "# of AWCs that reported unavailable electricity line or did not answer the question",
sum(num_awcs_conducted_cbe) AS "# AWCs conducted at least 2 CBE events",
sum(num_awcs_conducted_vhnd) AS "# AWCs conducted at least 1 VHNSD"
FROM "public"."awc_location_months_local" "awc_location_months" LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_months"."month" = "agg_awc"."month") AND
        ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
    )
WHERE "agg_awc"."aggregation_level"=5 AND "agg_awc"."month"='2019-12-01'
GROUP BY state_name
ORDER BY state_name
) TO '/tmp/monthly_stats4.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
