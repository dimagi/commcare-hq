SELECT
     state_name,
     SUM(num_launched_districts),
     SUM(num_launched_blocks),
     SUM(num_launched_awcs),
     SUM(num_launched_supervisors)
 FROM "agg_awc_daily_view"
 WHERE date='2020-02-03' AND aggregation_level=1
 GROUP BY state_name;
                                                                                                                                   QUERY PLAN
-- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  GroupAggregate  (cost=33.76..33.79 rows=1 width=42)
--    Group Key: awc_location.state_name
--    ->  Sort  (cost=33.76..33.76 rows=1 width=26)
--          Sort Key: awc_location.state_name
--          ->  Hash Join  (cost=13.47..33.75 rows=1 width=26)
--                Hash Cond: ((awc_location.state_id = agg_awc.state_id) AND (awc_location.district_id = agg_awc.district_id) AND (awc_location.block_id = agg_awc.block_id) AND (awc_location.supervisor_id = agg_awc.supervisor_id) AND (awc_location.doc_id = agg_awc.awc_id))
--                ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..19.85 rows=45 width=174)
--                      Index Cond: (aggregation_level = 1)
--                ->  Hash  (cost=12.57..12.57 rows=21 width=180)
--                      ->  Append  (cost=0.00..12.57 rows=21 width=180)
--                            ->  Seq Scan on agg_awc_daily agg_awc  (cost=0.00..0.00 rows=1 width=180)
--                                  Filter: ((aggregation_level = 1) AND (date = '2020-02-03'::date))
--                            ->  Index Scan using "agg_awc_daily_2020-02-03_aggregation_level_idx" on "agg_awc_daily_2020-02-03" agg_awc_1  (cost=0.42..12.47 rows=20 width=180)
--                                  Index Cond: (aggregation_level = 1)
--                                  Filter: (date = '2020-02-03'::date)
-- (15 rows)