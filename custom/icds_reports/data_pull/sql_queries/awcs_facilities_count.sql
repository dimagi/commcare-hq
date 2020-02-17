SELECT   state_name,
         count(*) filter (WHERE infra_clean_water=1) AS "# of AWCs that reported available drinking water",
         count(*) filter (WHERE infra_clean_water IS NULL OR infra_clean_water=0) AS "# of AWCs that reported unavailable drinking water or did not answer the question",
         count(*) filter (WHERE infra_functional_toilet=1) AS "# of AWCs that reported available functional toilet",
         count(*) filter (WHERE infra_functional_toilet IS NULL OR infra_functional_toilet=0) AS "# of AWCs that reported unavailable functional toilet or did not answer the question",
         count(*) filter (WHERE infantometer=1) AS "# of AWCs that reported usable infantometer",
         count(*) filter (WHERE infantometer IS NULL OR infantometer=0) AS "# of AWCs that reported unavailable usable infantometer or did not answer the question",
         count(*) filter (WHERE stadiometer=1) AS "# of AWCs that reported usable stadiometer",
         count(*) filter (WHERE stadiometer IS NULL OR stadiometer=0) AS "# of AWCs that reported unavailable usable stadiometer or did not answer the question",
         count(*) filter (WHERE infra_medicine_kits=1) AS "# of AWCs that reported available medicine kit",
         count(*) filter (WHERE infra_medicine_kits IS NULL OR infra_medicine_kits=0) AS "# of AWCs that reported unavailable medicine kit or did not answer the question",
         count(*) filter (WHERE infra_infant_weighing_scale=1) AS "# of AWCs that reported available infant weighing scale",
         count(*) filter (WHERE infra_infant_weighing_scale IS NULL OR infra_infant_weighing_scale=0) AS "# of AWCs that reported unavailable infant weighing scale or did not answer the question",
         count(*) filter (WHERE infra_adult_weighing_scale=1) AS "# of AWCs that reported available mother and child weighing scale",
         count(*) filter (WHERE infra_adult_weighing_scale IS NULL OR infra_adult_weighing_scale=0) AS "# of AWCs that reported unavailable mother and child weighing scale or did not answer the question"
FROM     agg_awc_monthly
WHERE    aggregation_level=5
AND      month='{month}'
GROUP BY state_name
