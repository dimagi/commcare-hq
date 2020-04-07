
COPY(SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code,
    CASE WHEN (agg.num_awcs_conducted_vhnd IS NOT NULL AND agg.num_awcs_conducted_vhnd>0) THEN 'Y'
        ELSE 'N'
    END as vhnd_conducted_month_executes,
    CASE WHEN num_launched_awcs=1 THEN 'Launched'
        ELSE 'Not Launched'
    END as launched_status
FROM
    "awc_location_local" awc LEFT JOIN "agg_awc" agg ON (
        awc.supervisor_id=agg.supervisor_id and
        awc.awc_id = agg.awc_id AND
        awc.supervisor_id=agg.supervisor_id
    )
    where agg.month = "%(month_execute)s"
    and awc.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc.aggregation_level=5) TO '/tmp/%(month_execute)s/ap_%(month_execute)s_vhnd.csv' DELIMITER ',' CSV HEADER
