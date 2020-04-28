COPY(SELECT
    awc.district_name,
    awc.state_name,
    agg.state_id,
    agg.district_id,
    CASE WHEN agg.month='%(month_1)s' THEN agg.num_launched_awcs ELSE 0 END as awcs_with_smart_phones_%(column_1)s,
    CASE WHEN agg.month='%(month_2)s' THEN agg.num_launched_awcs ELSE 0 END as awcs_with_smart_phones_%(column_2)s,
    CASE WHEN agg.month='%(month_3)s' THEN agg.num_launched_awcs ELSE 0 END as awcs_with_smart_phones_%(column_3)s,
    CASE WHEN agg.month='%(month_1)s' THEN agg.awc_num_open ELSE 0 END as awcs_with_smart_phones_using_icds_cas_%(column_1)s,
    CASE WHEN agg.month='%(month_2)s' THEN agg.awc_num_open ELSE 0 END as awcs_with_smart_phones_using_icds_cas_%(column_2)s,
    CASE WHEN agg.month='%(month_3)s' THEN agg.awc_num_open ELSE 0 END as awcs_with_smart_phones_using_icds_cas_%(column_3)s,
    CASE WHEN agg.month='%(month_1)s' THEN agg.cbe_conducted ELSE 0 END as cbe_conducted_%(column_1)s,
    CASE WHEN agg.month='%(month_2)s' THEN agg.cbe_conducted ELSE 0 END as cbe_conducted_%(column_2)s,
    CASE WHEN agg.month='%(month_3)s' THEN agg.cbe_conducted ELSE 0 END as cbe_conducted_%(column_3)s,
    CASE WHEN agg.month='%(month_1)s' THEN agg.vhnd_conducted ELSE 0 END as vhnd_conducted_%(column_1)s,
    CASE WHEN agg.month='%(month_2)s' THEN agg.vhnd_conducted ELSE 0 END as vhnd_conducted_%(column_2)s,
    CASE WHEN agg.month='%(month_3)s' THEN agg.vhnd_conducted ELSE 0 END as vhnd_conducted_%(column_3)s
    FROM agg_awc agg
    LEFT OUTER JOIN awc_location_local awc ON (
        awc.district_id = agg.district_id AND
        awc.aggregation_level = agg.aggregation_level
    ) WHERE agg.aggregation_level = 2
    AND agg.month in ('%(month_1)s', '%(month_2)s', '%(month_3)s') ) TO '/tmp/%(name)s/district_data_pull_1.csv' DELIMITER ',' CSV HEADER

--   QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------
--  Merge Left Join  (cost=303.22..341.88 rows=766 width=133)
--    Merge Cond: (agg.district_id = awc.district_id)
--    Join Filter: (awc.aggregation_level = agg.aggregation_level)
--    ->  Sort  (cost=123.96..125.87 rows=766 width=90)
--          Sort Key: agg.district_id
--          ->  Append  (cost=0.00..87.26 rows=766 width=90)
--                ->  Seq Scan on agg_awc agg  (cost=0.00..0.00 rows=1 width=88)
--                      Filter: ((aggregation_level = 2) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[])))
--                ->  Seq Scan on "agg_awc_2019-04-01_2" agg_1  (cost=0.00..24.80 rows=234 width=90)
--                      Filter: ((aggregation_level = 2) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[])))
--                ->  Seq Scan on "agg_awc_2019-05-01_2" agg_2  (cost=0.00..28.19 rows=258 width=90)
--                      Filter: ((aggregation_level = 2) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[])))
--                ->  Seq Scan on "agg_awc_2019-06-01_2" agg_3  (cost=0.00..30.44 rows=273 width=90)
--                      Filter: ((aggregation_level = 2) AND (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[])))
--    ->  Sort  (cost=179.27..180.18 rows=367 width=55)
--          Sort Key: awc.district_id
--          ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc  (cost=0.42..163.63 rows=367 width=55)
--                Index Cond: (aggregation_level = 2)
