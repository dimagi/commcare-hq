SELECT SUM(num_rations_distributed) as chm_month_jan_2020 FROM child_health_monthly chm LEFT OUTER JOIN awc_location awc ON (awc.doc_id = chm.awc_id AND awc.supervisor_id = chm.supervisor_id) WHERE awc.state_is_test = 0 AND chm.month='2020-01-01';
SELECT SUM(num_rations_distributed) as chm_month_feb_2020 FROM child_health_monthly chm LEFT OUTER JOIN awc_location awc ON (awc.doc_id = chm.awc_id AND awc.supervisor_id = chm.supervisor_id) WHERE awc.state_is_test = 0 AND chm.month='2020-02-01';
SELECT SUM(num_rations_distributed) as chm_month_march_2020 FROM child_health_monthly chm LEFT OUTER JOIN awc_location awc ON (awc.doc_id = chm.awc_id AND awc.supervisor_id = chm.supervisor_id) WHERE awc.state_is_test = 0 AND chm.month='2020-03-01';
SELECT SUM(num_rations_distributed) as chm_month_april_2020 FROM child_health_monthly chm LEFT OUTER JOIN awc_location awc ON (awc.doc_id = chm.awc_id AND awc.supervisor_id = chm.supervisor_id) WHERE awc.state_is_test = 0 AND chm.month='2020-04-01';

SELECT SUM(num_rations_distributed) as ccs_month_jan_2020 FROM ccs_record_monthly ccs LEFT OUTER JOIN awc_location awc ON (awc.doc_id = ccs.awc_id AND awc.supervisor_id = ccs.supervisor_id) WHERE awc.state_is_test = 0 AND ccs.month='2020-01-01';
SELECT SUM(num_rations_distributed) as ccs_month_feb_2020 FROM ccs_record_monthly ccs LEFT OUTER JOIN awc_location awc ON (awc.doc_id = ccs.awc_id AND awc.supervisor_id = ccs.supervisor_id) WHERE awc.state_is_test = 0 AND ccs.month='2020-02-01';
SELECT SUM(num_rations_distributed) as ccs_month_march_2020 FROM ccs_record_monthly ccs LEFT OUTER JOIN awc_location awc ON (awc.doc_id = ccs.awc_id AND awc.supervisor_id = ccs.supervisor_id) WHERE awc.state_is_test = 0 AND ccs.month='2020-03-01';
SELECT SUM(num_rations_distributed) as ccs_month_april_2020 FROM ccs_record_monthly ccs LEFT OUTER JOIN awc_location awc ON (awc.doc_id = ccs.awc_id AND awc.supervisor_id = ccs.supervisor_id) WHERE awc.state_is_test = 0 AND ccs.month='2020-04-01';

--
-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Aggregate  (cost=0.00..0.00 rows=0 width=0)
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Finalize Aggregate  (cost=215152.34..215152.35 rows=1 width=8)
--                      ->  Gather  (cost=215151.92..215152.33 rows=4 width=8)
--                            Workers Planned: 4
--                            ->  Partial Aggregate  (cost=214151.92..214151.93 rows=1 width=8)
--                                  ->  Merge Join  (cost=0.99..214151.90 rows=10 width=4)
--                                        Merge Cond: (awc.doc_id = chm.awc_id)
--                                        Join Filter: (chm.supervisor_id = awc.supervisor_id)
--                                        ->  Parallel Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..108838.79 rows=194657 width=63)
--                                              Filter: (state_is_test = 0)
--                                        ->  Materialize  (cost=0.43..99297.03 rows=875076 width=70)
--                                              ->  Merge Append  (cost=0.43..97109.34 rows=875076 width=70)
--                                                    Sort Key: chm.awc_id
--                                                    ->  Index Scan using "child_health_monthly_2020-01-01_403772_awc_id_idx" on "child_health_monthly_2020-01-01_403772" chm  (cost=0.42..88358.57 rows=875076 width=70)
--                                                          Filter: (month = '2020-01-01'::date)

--
-- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Aggregate  (cost=0.00..0.00 rows=0 width=0)
--    ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--          Task Count: 64
--          Tasks Shown: One of 64
--          ->  Task
--                Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                ->  Aggregate  (cost=182964.38..182964.39 rows=1 width=8)
--                      ->  Gather  (cost=1001.11..182964.36 rows=5 width=4)
--                            Workers Planned: 5
--                            ->  Nested Loop  (cost=1.10..181963.86 rows=1 width=4)
--                                  ->  Parallel Index Scan using crm_supervisor_person_month_idx_102712 on ccs_record_monthly_102712 ccs  (cost=0.56..148939.33 rows=23902 width=70)
--                                        Index Cond: (month = '2020-01-01'::date)
--                                  ->  Index Scan using awc_location_indx6_102840 on awc_location_102840 awc  (cost=0.55..1.37 rows=1 width=63)
--                                        Index Cond: (doc_id = ccs.awc_id)
--                                        Filter: ((state_is_test = 0) AND (ccs.supervisor_id = supervisor_id))
-- (15 rows)
