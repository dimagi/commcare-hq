COPY(SELECT
    awc.district_name,
    awc.state_name,
    agg.state_id,
    agg.district_id,
    CASE WHEN agg.month='{month_1}' THEN agg.cf_initiation_in_month ELSE 0 END as cf_initiation_in_month_{column_1},
    CASE WHEN agg.month='{month_2}' THEN agg.cf_initiation_in_month ELSE 0 END as cf_initiation_in_month_{column_2},
    CASE WHEN agg.month='{month_3}' THEN agg.cf_initiation_in_month ELSE 0 END as cf_initiation_in_month_{column_3},
    CASE WHEN agg.month='{month_1}' THEN agg.cf_initiation_eligible ELSE 0 END as cf_initiation_eligible_{column_1},
    CASE WHEN agg.month='{month_2}' THEN agg.cf_initiation_eligible ELSE 0 END as cf_initiation_eligible_{column_2},
    CASE WHEN agg.month='{month_3}' THEN agg.cf_initiation_eligible ELSE 0 END as cf_initiation_eligible_{column_3}
    FROM agg_child_health agg
    LEFT OUTER JOIN awc_location_local awc ON (
        awc.district_id = agg.district_id AND
        awc.aggregation_level = agg.aggregation_level
    ) WHERE agg.aggregation_level = 2
    AND agg.month in ('{month_1}', '{month_2}', '{month_3}') ) TO '/tmp/%(name)s/district_data_pull_2.csv' DELIMITER ',' CSV HEADER

SELECT
    awc.district_name,
    awc.state_name,
    agg.state_id,
    agg.district_id,
    CASE WHEN agg.month='2019-03-01' THEN agg.cf_initiation_in_month ELSE 0 END as cf_initiation_in_month_column_1,
    CASE WHEN agg.month='2019-04-01' THEN agg.cf_initiation_in_month ELSE 0 END as cf_initiation_in_month_column_2,
    CASE WHEN agg.month='2019-05-01' THEN agg.cf_initiation_in_month ELSE 0 END as cf_initiation_in_month_column_3,
    CASE WHEN agg.month='2019-03-01' THEN agg.cf_initiation_eligible ELSE 0 END as cf_initiation_eligible_column_1,
    CASE WHEN agg.month='2019-04-01' THEN agg.cf_initiation_eligible ELSE 0 END as cf_initiation_eligible_column_2,
    CASE WHEN agg.month='2019-05-01' THEN agg.cf_initiation_eligible ELSE 0 END as cf_initiation_eligible_column_3
    FROM agg_child_health agg
    LEFT OUTER JOIN awc_location_local awc ON (
        awc.district_id = agg.district_id AND
        awc.aggregation_level = agg.aggregation_level
    ) WHERE agg.aggregation_level = 2
    AND agg.month in ('2019-03-01', '2019-04-01', '2019-05-01')
