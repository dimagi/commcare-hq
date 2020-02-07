SELECT
    num_launched_states,
    num_launched_districts,
    num_launched_blocks,
    num_launched_awcs,
    num_launched_supervisors
FROM 'agg_awc_daily_view' WHERE date='2020-02-03' AND aggregation_level=1;
