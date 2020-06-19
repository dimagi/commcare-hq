COPY(
SELECT state_name, district_name, thr_given_21_days, total_thr_candidates FROM service_delivery_monthly WHERE aggregation_level=2 AND month='2020-04-01';
) TO '/tmp/thr_april_2020.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

COPY(
SELECT state_name, district_name, thr_given_21_days, total_thr_candidates FROM service_delivery_monthly WHERE aggregation_level=2 AND month='2020-05-01';
) TO '/tmp/thr_may_2020.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

--
--
-- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Subquery Scan on service_delivery_monthly  (cost=357.57..357.64 rows=1 width=35)
--    ->  GroupAggregate  (cost=357.57..357.63 rows=1 width=426)
--          Group Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, agg_awc.month, agg_awc.num_launched_awcs, agg_awc.num_awcs_conducted_cbe, agg_awc.valid_visits, agg_awc.expected_visits, agg_awc.num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
--          ->  Sort  (cost=357.57..357.58 rows=1 width=358)
--                Sort Key: awc_location.doc_id, awc_location.supervisor_id, awc_location.block_id, awc_location.district_id, awc_location.state_id, agg_awc.num_launched_awcs, agg_awc.num_awcs_conducted_cbe, agg_awc.valid_visits, agg_awc.expected_visits, agg_awc.num_awcs_conducted_vhnd, (sum(agg_ccs_record.rations_21_plus_distributed)), (sum(agg_ccs_record.thr_eligible))
--                ->  Nested Loop Left Join  (cost=306.11..357.56 rows=1 width=358)
--                      Join Filter: ((agg_ccs_record.month = months.start_date) AND (agg_ccs_record.aggregation_level = awc_location.aggregation_level) AND (agg_ccs_record.state_id = awc_location.state_id) AND (agg_ccs_record.district_id = awc_location.district_id) AND (agg_ccs_record.block_id = awc_location.block_id) AND (agg_ccs_record.supervisor_id = awc_location.supervisor_id) AND (agg_ccs_record.awc_id = awc_location.doc_id))
--                      ->  Nested Loop Left Join  (cost=217.22..259.17 rows=1 width=346)
--                            Join Filter: (agg_child_health.month = months.start_date)
--                            ->  Nested Loop  (cost=217.22..255.65 rows=1 width=338)
--                                  ->  Hash Join  (cost=217.22..254.12 rows=1 width=334)
--                                        Hash Cond: ((agg_awc.state_id = awc_location.state_id) AND (agg_awc.district_id = awc_location.district_id) AND (agg_awc.block_id = awc_location.block_id) AND (agg_awc.supervisor_id = awc_location.supervisor_id) AND (agg_awc.awc_id = awc_location.doc_id))
--                                        ->  Append  (cost=0.00..31.39 rows=420 width=106)
--                                              ->  Seq Scan on agg_awc  (cost=0.00..0.00 rows=1 width=188)
--                                                    Filter: ((month = '2020-05-01'::date) AND (aggregation_level = 2))
--                                              ->  Seq Scan on "agg_awc_2020-05-01_2"  (cost=0.00..29.29 rows=419 width=106)
--                                                    Filter: ((month = '2020-05-01'::date) AND (aggregation_level = 2))
--                                        ->  Hash  (cost=207.97..207.97 rows=411 width=310)
--                                              ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local awc_location  (cost=0.42..207.97 rows=411 width=310)
--                                                    Index Cond: (aggregation_level = 2)
--                                  ->  Seq Scan on icds_months_local months  (cost=0.00..1.52 rows=1 width=4)
--                                        Filter: (start_date = '2020-05-01'::date)
--                            ->  Append  (cost=0.00..3.49 rows=2 width=177)
--                                  ->  Seq Scan on agg_child_health  (cost=0.00..0.00 rows=1 width=176)
--                                        Filter: ((month = '2020-05-01'::date) AND (aggregation_level = 2) AND (aggregation_level = awc_location.aggregation_level) AND (state_id = awc_location.state_id) AND (district_id = awc_location.district_id) AND (block_id = awc_location.block_id) AND (supervisor_id = awc_location.supervisor_id) AND (awc_id = awc_location.doc_id))
--                                  ->  Index Scan using staging_agg_child_health_aggregation_level_district_id_idx14 on "agg_child_health_2020-05-01"  (cost=0.56..3.48 rows=1 width=177)
--                                        Index Cond: ((aggregation_level = awc_location.aggregation_level) AND (aggregation_level = 2) AND (district_id = awc_location.district_id))
--                                        Filter: ((month = '2020-05-01'::date) AND (state_id = awc_location.state_id) AND (block_id = awc_location.block_id) AND (supervisor_id = awc_location.supervisor_id) AND (awc_id = awc_location.doc_id))
--                      ->  HashAggregate  (cost=88.89..90.89 rows=200 width=102)
--                            Group Key: agg_ccs_record.state_id, agg_ccs_record.district_id, agg_ccs_record.block_id, agg_ccs_record.supervisor_id, agg_ccs_record.awc_id, agg_ccs_record.aggregation_level, agg_ccs_record.month
--                            ->  Append  (cost=0.00..65.64 rows=1033 width=94)
--                                  ->  Seq Scan on agg_ccs_record  (cost=0.00..0.00 rows=1 width=176)
--                                        Filter: ((month = '2020-05-01'::date) AND (aggregation_level = 2))
--                                  ->  Seq Scan on "agg_ccs_record_2020-05-01_2"  (cost=0.00..60.48 rows=1032 width=94)
--                                        Filter: ((month = '2020-05-01'::date) AND (aggregation_level = 2))
-- (35 rows)
