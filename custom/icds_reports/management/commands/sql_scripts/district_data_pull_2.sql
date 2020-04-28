COPY(SELECT
    awc.district_name,
    awc.state_name,
    agg.state_id,
    agg.district_id,
    SUM(CASE WHEN agg.month='%(month_1)s' THEN agg.cf_initiation_in_month ELSE 0 END) as cf_initiation_in_month_%(column_1)s,
    SUM(CASE WHEN agg.month='%(month_2)s' THEN agg.cf_initiation_in_month ELSE 0 END) as cf_initiation_in_month_%(column_2)s,
    SUM(CASE WHEN agg.month='%(month_3)s' THEN agg.cf_initiation_in_month ELSE 0 END) as cf_initiation_in_month_%(column_3)s,
    SUM(CASE WHEN agg.month='%(month_1)s' THEN agg.cf_initiation_eligible ELSE 0 END) as cf_initiation_eligible_%(column_1)s,
    SUM(CASE WHEN agg.month='%(month_2)s' THEN agg.cf_initiation_eligible ELSE 0 END) as cf_initiation_eligible_%(column_2)s,
    SUM(CASE WHEN agg.month='%(month_3)s' THEN agg.cf_initiation_eligible ELSE 0 END) as cf_initiation_eligible_%(column_3)s
    FROM agg_child_health agg
    LEFT OUTER JOIN awc_location_local awc ON (
        awc.district_id = agg.district_id AND
        awc.aggregation_level = agg.aggregation_level
    ) WHERE agg.aggregation_level = 2
    AND agg.month in ('%(month_1)s', '%(month_2)s', '%(month_3)s') GROUP BY agg.district_id, awc.district_name, awc.state_name) TO '/tmp/%(name)s/district_data_pull_2.csv' DELIMITER ',' CSV HEADER


-- QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------------
--  HashAggregate  (cost=1951.59..2033.17 rows=8158 width=100)
--    Group Key: agg.district_id, awc.district_name, awc.state_name
--    ->  Merge Left Join  (cost=1478.63..1645.67 rows=8158 width=64)
--          Merge Cond: (agg.district_id = awc.district_id)
--          Join Filter: (awc.aggregation_level = agg.aggregation_level)
--          ->  Sort  (cost=1299.37..1319.76 rows=8158 width=49)
--                Sort Key: agg.district_id
--                ->  Append  (cost=0.00..769.34 rows=8158 width=49)
--                      ->  Seq Scan on agg_child_health agg  (cost=0.00..0.00 rows=1 width=48)
--                            Filter: ((aggregation_level = 2) AND (month = ANY ('%(2019-03-01,2019-04-01,2019-05-01}'::date[])))
--                      ->  Seq Scan on "agg_child_health_2019-04-01_2" agg_1  (cost=0.00..198.67 rows=2441 width=49)
--                            Filter: ((aggregation_level = 2) AND (month = ANY ('{2019-03-01,2019-04-01,2019-05-01}'::date[])s))
--                      ->  Seq Scan on "agg_child_health_2019-03-01_2" agg_2  (cost=0.00..247.79 rows=2264 width=49)
--                            Filter: ((aggregation_level = 2) AND (month = ANY ('{2019-03-01,2019-04-01,2019-05-01}'::date[])))
--                      ->  Seq Scan on "agg_child_health_2019-05-01_2" agg_3  (cost=0.00..282.10 rows=3452 width=49)
--                            Filter: ((aggregation_level = 2) AND (month = ANY ('{2019-03-01,2019-04-01,2019-05-01}'::date[])))
--          ->  Sort  (cost=179.27..180.18 rows=367 width=55)
--                Sort Key: awc.district_id
--                ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc  (cost=0.42..163.63 rows=367 width=55)
--                      Index Cond: (aggregation_level = 2)
