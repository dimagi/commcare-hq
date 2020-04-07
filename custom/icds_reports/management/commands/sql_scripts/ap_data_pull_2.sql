COPY(SELECT
    awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code,
    SUM(CASE WHEN (agg.num_awcs_conducted_vhnd IS NOT NULL AND agg.num_awcs_conducted_vhnd>0 AND agg.month='%(month_1)s') THEN 1 ELSE 0 END) as vhnd_conducted_%(column_1)s,
    SUM(CASE WHEN agg.num_launched_awcs=1 AND agg.month='%(month_1)s' THEN 1 ELSE 0 END) as launched_status_%(column_1)s,

    SUM(CASE WHEN (agg.num_awcs_conducted_vhnd IS NOT NULL AND agg.num_awcs_conducted_vhnd>0 AND agg.month='%(month_2)s') THEN 1 ELSE 0 END) as vhnd_conducted_%(column_2)s,
    SUM(CASE WHEN agg.num_launched_awcs=1 AND agg.month='%(month_2)s' THEN 1 ELSE 0 END) as launched_status_%(column_2)s,

    SUM(CASE WHEN (agg.num_awcs_conducted_vhnd IS NOT NULL AND agg.num_awcs_conducted_vhnd>0 AND agg.month='%(month_3)s') THEN 1 ELSE 0 END) as vhnd_conducted_%(column_3)s,
    SUM(CASE WHEN agg.num_launched_awcs=1 AND agg.month='%(month_3)s' THEN 1 ELSE 0 END) as launched_status_%(column_3)s
FROM
    "awc_location_local" awc LEFT JOIN "agg_awc" agg ON (
        awc.supervisor_id=agg.supervisor_id and
        awc.doc_id = agg.awc_id AND
        awc.supervisor_id=agg.supervisor_id and
        agg.month in ('%(month_1)s','%(month_2)s','%(month_3)s')
    )
    where awc.state_id='f98e91aa003accb7b849a0f18ebd7039' and awc.aggregation_level=5
    group by awc.state_name,
    awc.district_name,
    awc.block_name,
    awc.supervisor_name,
    awc.awc_name,
    awc.awc_site_code) TO '/tmp/%(name)s/ap_data_pull_2.csv' DELIMITER ',' CSV HEADER

--                                                                QUERY PLAN
-- ----------------------------------------------------------------------------------------------------------------------------------------
--  Gather  (cost=298255.09..301832.65 rows=5 width=280)
--    Workers Planned: 4
--    ->  Merge Join  (cost=297255.09..300832.15 rows=1 width=280)
--          Merge Cond: ((agg_15.supervisor_id = awc.supervisor_id) AND (agg_15.awc_id = awc.doc_id))
--          ->  Sort  (cost=220727.65..221733.89 rows=402493 width=77)
--                Sort Key: agg_15.supervisor_id, agg_15.awc_id
--                ->  Parallel Append  (cost=0.00..162307.36 rows=402493 width=77)
--                      ->  Parallel Seq Scan on "agg_awc_2019-06-01_5" agg_15  (cost=0.00..61171.33 rows=150715 width=78)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-05-01_5" agg_10  (cost=0.00..49717.43 rows=127958 width=78)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-04-01_5" agg_5  (cost=0.00..42845.22 rows=108743 width=78)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-06-01_4" agg_14  (cost=0.00..2095.27 rows=10783 width=49)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-05-01_4" agg_9  (cost=0.00..1931.26 rows=10346 width=49)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-04-01_4" agg_4  (cost=0.00..1635.53 rows=9275 width=49)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-06-01_3" agg_13  (cost=0.00..301.57 rows=1642 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-05-01_3" agg_8  (cost=0.00..278.47 rows=1562 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-04-01_3" agg_3  (cost=0.00..227.89 rows=1374 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-06-01_2" agg_12  (cost=0.00..28.21 rows=161 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-05-01_2" agg_7  (cost=0.00..26.09 rows=152 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-04-01_2" agg_2  (cost=0.00..21.89 rows=138 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-06-01_1" agg_11  (cost=0.00..5.25 rows=18 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-05-01_1" agg_6  (cost=0.00..5.24 rows=18 width=20)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on "agg_awc_2019-04-01_1" agg_1  (cost=0.00..4.24 rows=2 width=76)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--                      ->  Parallel Seq Scan on agg_awc agg  (cost=0.00..0.00 rows=1 width=76)
--                            Filter: (month = ANY ('{2019-04-01,2019-05-01,2019-06-01}'::date[]))
--          ->  Materialize  (cost=76527.44..76806.60 rows=55832 width=151)
--                ->  Sort  (cost=76527.44..76667.02 rows=55832 width=151)
--                      Sort Key: awc.supervisor_id, awc.doc_id
--                      ->  Index Scan using awc_location_local_pkey on awc_location_local awc  (cost=0.68..69665.42 rows=55832 width=151)
--                            Index Cond: (state_id = 'f98e91aa003accb7b849a0f18ebd7039'::text)
--                            Filter: (aggregation_level = 5)
