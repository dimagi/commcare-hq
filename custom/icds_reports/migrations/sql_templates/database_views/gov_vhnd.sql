DROP VIEW IF EXISTS gov_vhnd_view CASCADE;
CREATE VIEW gov_vhnd_view AS
SELECT
"awc_location_local"."state_id" AS "state_id",
"awc_location_local"."doc_id" AS "awc_id",
"awc_location_local"."awc_site_code" AS "awc_code",
agg_awc.month as month,
COALESCE(icds_dashboard_gov_vhnd_forms.vhsnd_date_past_month, null) as vhsnd_date_past_month,
COALESCE(icds_dashboard_gov_vhnd_forms.anm_mpw_present,false) as anm_mpw_present,
COALESCE(icds_dashboard_gov_vhnd_forms.asha_present,false) as asha_present,
COALESCE(icds_dashboard_gov_vhnd_forms.child_immu,false) as child_immu,
COALESCE(icds_dashboard_gov_vhnd_forms.anc_today,false) as anc_today

FROM "awc_location_local"
LEFT join agg_awc on (
        ("awc_location_local"."doc_id" = "agg_awc"."awc_id") and
        ("agg_awc"."aggregation_level" = 5)
        )

LEFT join icds_dashboard_gov_vhnd_forms on (
    ("icds_dashboard_gov_vhnd_forms"."awc_id" = "agg_awc"."awc_id") and
    ("icds_dashboard_gov_vhnd_forms"."month" = "agg_awc"."month")
)

where awc_location_local.state_is_test<>1 and awc_location_local.district_is_test<>1 and
 awc_location_local.block_is_test<>1 and awc_location_local.supervisor_is_test<>1 and awc_location_local.awc_is_test<>1
 and awc_location_local.aggregation_level = 5 and "agg_awc"."is_launched" = 'yes';
