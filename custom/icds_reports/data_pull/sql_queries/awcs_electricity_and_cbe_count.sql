SELECT    state_name,
          count(*) filter (WHERE electricity_awc=1) AS "# of AWCs that reported available electricity line",
          count(*) filter (WHERE electricity_awc IS NULL OR electricity_awc=0) AS "# of AWCs that reported unavailable electricity line or did not answer the question",
          sum(num_awcs_conducted_cbe)  AS "# AWCs conducted at least 2 CBE events",
          sum(num_awcs_conducted_vhnd) AS "# AWCs conducted at least 1 VHNSD"
FROM      "public"."awc_location_months_local" "awc_location_months"
INNER JOIN "public"."agg_awc" "agg_awc"
ON        (("awc_location_months"."month" = "agg_awc"."month") AND
           ("awc_location_months"."aggregation_level" = "agg_awc"."aggregation_level") AND
           ("awc_location_months"."state_id" = "agg_awc"."state_id") AND
           ("awc_location_months"."district_id" = "agg_awc"."district_id") AND
           ("awc_location_months"."block_id" = "agg_awc"."block_id") AND
           ("awc_location_months"."supervisor_id" = "agg_awc"."supervisor_id") AND
           ("awc_location_months"."awc_id" = "agg_awc"."awc_id")
          )
WHERE     "agg_awc"."aggregation_level"=5
AND       "agg_awc"."month"='{month}'
GROUP BY  state_name
