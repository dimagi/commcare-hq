SELECT
     state_name,
     SUM(num_launched_awcs),
     SUM(num_launched_supervisors)
 FROM 'agg_awc_daily_view' GROUP BY state_id WHERE date='2020-02-03' AND aggregation_level=1;
