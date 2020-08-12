 SELECT state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,
    vhsnd_date_past_month
FROM agg_awc_monthly INNER JOIN "ucr_icds-cas_static-vhnd_form_28e7fd58" vhnd_ucr ON agg_awc_monthly.awc_id=vhnd_ucr.awc_id AND vhnd_ucr.vhsnd_date_past_month>='{month}' AND vhnd_ucr.vhsnd_date_past_month<'{month}'::DATE + '1 month'::interval
WHERE agg_awc_monthly.aggregation_level=5 AND agg_awc_monthly.month='{month}' AND agg_awc_monthly.state_is_test<>1 AND agg_awc_monthly.num_launched_awcs=1 ORDER BY state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    awc_site_code,
    vhsnd_date_past_month
