DROP VIEW IF EXISTS mwcd_report CASCADE;
CREATE VIEW mwcd_report AS
SELECT

"awc_location_local"."state_id" AS "state_id",
"awc_location_local"."state_name" AS "state_name",
"awc_location_local"."state_site_code" AS "state_site_code",
"awc_location_local"."aggregation_level" AS "aggregation_level",
agg_awc.month as month,
COALESCE(agg_awc.num_launched_awcs,0) as num_launched_awcs,
COALESCE(agg_awc.num_launched_districts,0) as num_launched_districts,
COALESCE(agg_awc.num_launched_states,0) as num_launched_states,
COALESCE(agg_awc.awc_with_gm_devices,0) as awc_with_gm_devices,
COALESCE(agg_awc.cases_household,0) as cases_household,
COALESCE(agg_awc.cases_child_health,0) as cases_child_health,
COALESCE(agg_awc.cases_ccs_pregnant+ agg_awc.cases_ccs_lactating,0) as total_mothers,
COALESCE(agg_ls.num_supervisor_launched,0) as num_ls_launched

FROM (select * from "public"."awc_location_local" where aggregation_level=1) "awc_location_local"
LEFT join agg_awc on (
        ("agg_awc"."state_id" = "awc_location_local"."state_id") AND
        ("agg_awc"."aggregation_level" = "awc_location_local"."aggregation_level") AND
        ("agg_awc"."aggregation_level" = 1)
        )
LEFT JOIN agg_ls on (
        ("agg_ls"."state_id" = "awc_location_local"."state_id") AND
        ("agg_ls"."aggregation_level" = "awc_location_local"."aggregation_level") AND
        ("agg_ls"."aggregation_level" = 1) AND
        ("agg_ls"."month" = "agg_awc"."month")

)

where awc_location_local.aggregation_level = 1 and awc_location_local.state_is_test<>1;
