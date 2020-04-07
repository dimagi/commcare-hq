COPY(SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code,
    SUM(CASE WHEN chm.num_rations_distributed>=21 THEN 1 ELSE 0 END) as thr_count_ccs,
    SUM(CASE WHEN chm.thr_eligible=1 THEN 1 ELSE 0 END) as thr_eligible_ccs
FROM
    "awc_location" awc LEFT JOIN "ccs_record_monthly" chm ON (
        chm.supervisor_id=awc.supervisor_id and
        chm.awc_id = awc.doc_id
    )
    where chm.month = "%(month_execute)s"
    and awc.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc.aggregation_level=5
GROUP by awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code) TO '/tmp/%(month_execute)s/ap_%(month_execute)s_thr_ccs.csv' DELIMITER ',' CSV HEADER
