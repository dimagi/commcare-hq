COPY(SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code,
    CASE WHEN (SUM(CASE WHEN chm.recorded_weight IS NOT NULL THEN 1 ELSE 0 END)/count(*))::float>=0.6 THEN 'Y'
        ELSE 'N'
    END as gm_%(month_execute)s,
    CASE WHEN (SUM(CASE WHEN chm.num_rations_distributed>=21 THEN 1 ELSE 0 END)/SUM(CASE WHEN chm.age_tranche::int>=6 THEN 1 ELSE 0 END))>=0.6 THEN 'Y'
        ELSE 'N'
    END as thr_%(month_execute)s
FROM
    "awc_location" awc LEFT JOIN "child_health_monthly" chm ON (
        chm.supervisor_id=awc.supervisor_id and
        chm.awc_id = awc.doc_id and
        chm.valid_in_month=1 AND
        chm.age_tranche::int<=36
    )
    where chm.month = '%(month_execute)s'
    and awc.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc.aggregation_level=5
GROUP by awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code) TO '/tmp/ap_%(month_execute)s_thr.csv' DELIMITER ',' CSV HEADER
