COPY(SELECT
    awc.district_name,
    awc.state_name,
    agg.state_id,
    agg.district_id,
    CASE WHEN agg.month='{month_1}' THEN agg.num_launched_awcs ELSE 0 END as awcs_with_smart_phones_{column_1},
    CASE WHEN agg.month='{month_2}' THEN agg.num_launched_awcs ELSE 0 END as awcs_with_smart_phones_{column_2},
    CASE WHEN agg.month='{month_3}' THEN agg.num_launched_awcs ELSE 0 END as awcs_with_smart_phones_{column_3},
    CASE WHEN agg.month='{month_1}' THEN agg.awc_num_open ELSE 0 END as awcs_with_smart_phones_using_icds_cas_{column_1},
    CASE WHEN agg.month='{month_2}' THEN agg.awc_num_open ELSE 0 END as awcs_with_smart_phones_using_icds_cas_{column_2},
    CASE WHEN agg.month='{month_3}' THEN agg.awc_num_open ELSE 0 END as awcs_with_smart_phones_using_icds_cas_{column_3},
    CASE WHEN agg.month='{month_1}' THEN agg.cbe_conducted ELSE 0 END as cbe_conducted_{column_1},
    CASE WHEN agg.month='{month_2}' THEN agg.cbe_conducted ELSE 0 END as cbe_conducted_{column_2},
    CASE WHEN agg.month='{month_3}' THEN agg.cbe_conducted ELSE 0 END as cbe_conducted_{column_3},
    CASE WHEN agg.month='{month_1}' THEN agg.vhnd_conducted ELSE 0 END as vhnd_conducted_{column_1},
    CASE WHEN agg.month='{month_2}' THEN agg.vhnd_conducted ELSE 0 END as vhnd_conducted_{column_2},
    CASE WHEN agg.month='{month_3}' THEN agg.vhnd_conducted ELSE 0 END as vhnd_conducted_{column_3}
    FROM agg_awc agg
    LEFT OUTER JOIN awc_location_local awc ON (
        awc.district_id = agg.district_id AND
        awc.aggregation_level = agg.aggregation_level
    ) WHERE agg.aggregation_level = 2
    AND agg.month in ('{month_1}', '{month_2}', '{month_3}') ) TO '/tmp/%(name)s/district_data_pull_1.csv' DELIMITER ',' CSV HEADER
