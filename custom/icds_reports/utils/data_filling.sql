CREATE UNLOGGED TABLE tmp_sag_table as (
        select
            ucr.awc_id,
            ucr.supervisor_id,
            SUM(CASE WHEN ( (out_of_school or re_out_of_school) AND
                        (not admitted_in_school )) THEN 1 ELSE 0 END ) as girls_out_of_schoool,
            SUM(CASE WHEN '2008-04-30' > dob AND '2005-04-01' <= dob AND sex = 'F' THEN 1 ELSE 0 END) as cases_person_adolescent_girls_11_14_all_v2
            from "ucr_icds-cas_static-person_cases_v3_2ae0879a" ucr LEFT JOIN
                 "icds_dashboard_adolescent_girls_registration" adolescent_girls_table ON (
                    ucr.doc_id = adolescent_girls_table.person_case_id AND
                    ucr.supervisor_id = adolescent_girls_table.supervisor_id AND
                    adolescent_girls_table.month='2019-04-01'
                    )
            WHERE (opened_on <= '2019-04-30' AND
              (closed_on IS NULL OR closed_on >= '2019-04-01' )) AND
              migration_status IS DISTINCT FROM 1
              GROUP BY ucr.awc_id, ucr.supervisor_id
        ) ;
/*
 HashAggregate  (cost=0.00..0.00 rows=0 width=0)
   Group Key: remote_scan.awc_id, remote_scan.supervisor_id
   ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
         Task Count: 64
         Tasks Shown: One of 64
         ->  Task
               Node: host=100.71.184.232 port=6432 dbname=icds_ucr
               ->  Finalize GroupAggregate  (cost=412488.67..790495.64 rows=757473 width=82)
                     Group Key: ucr.awc_id, ucr.supervisor_id
                     ->  Gather Merge  (cost=412488.67..755768.06 rows=2715285 width=82)
                           Workers Planned: 5
                           ->  Partial GroupAggregate  (cost=411488.59..427780.30 rows=543057 width=82)
                                 Group Key: ucr.awc_id, ucr.supervisor_id
                                 ->  Sort  (cost=411488.59..412846.23 rows=543057 width=75)
                                       Sort Key: ucr.awc_id, ucr.supervisor_id
                                       ->  Hash Left Join  (cost=3.08..331490.89 rows=543057 width=75)
                                             Hash Cond: ((ucr.doc_id = adolescent_girls_table.person_case_id) AND (ucr.supervisor_id = adolescent_girls_table.supervisor_id))
                                             ->  Parallel Index Scan using "ix_ucr_icds-cas_static-person_cases_v3_2ae0879a_op_59aa0_103866" on "ucr_icds-cas_static-person_cases_v3_2ae0879a_103866" ucr  (cost=0.43..328637.19 rows=543057 width=109)
                                                   Index Cond: (opened_on <= '2019-04-30 00:00:00'::timestamp without time zone)
                                                   Filter: (((closed_on IS NULL) OR (closed_on >= '2019-04-01 00:00:00'::timestamp without time zone)) AND (migration_status IS DISTINCT FROM 1))
                                             ->  Hash  (cost=2.63..2.63 rows=1 width=73)
                                                   ->  Index Scan using icds_dashboard_adolescent_girls_registration_pkey_218364 on icds_dashboard_adolescent_girls_registration_218364 adolescent_girls_table  (cost=0.41..2.63 rows=1 width=73)
                                                         Index Cond: (month = '2019-04-01'::date)
(23 rows)
*/

UPDATE "agg_awc_2019-04-01_5" agg_awc
    set cases_person_adolescent_girls_11_14_out_of_school = ut.girls_out_of_schoool,
    cases_person_adolescent_girls_11_14_all_v2 = ut.cases_person_adolescent_girls_11_14_all_v2
 FROM
 (select * from tmp_sag_table) ut
 WHERE agg_awc.awc_id = ut.awc_id
 ;

UPDATE "agg_awc_2019-04-01_4" agg_awc
    set cases_person_adolescent_girls_11_14_out_of_school = ut.girls_out_of_schoool,
    cases_person_adolescent_girls_11_14_all_v2 = ut.cases_person_adolescent_girls_11_14_all_v2

FROM (
    select
    supervisor_id,
    sum(cases_person_adolescent_girls_11_14_out_of_school) as girls_out_of_schoool,
    sum(cases_person_adolescent_girls_11_14_all_v2) as cases_person_adolescent_girls_11_14_all_v2
    FROM "agg_awc_2019-04-01_5"
    WHERE awc_is_test<>1
    GROUP BY supervisor_id
)ut
where agg_awc.supervisor_id=ut.supervisor_id;


UPDATE "agg_awc_2019-04-01_3" agg_awc
    set cases_person_adolescent_girls_11_14_out_of_school = ut.girls_out_of_schoool,
    cases_person_adolescent_girls_11_14_all_v2 = ut.cases_person_adolescent_girls_11_14_all_v2
FROM (
    select
    block_id,
    sum(cases_person_adolescent_girls_11_14_out_of_school) as girls_out_of_schoool,
    sum(cases_person_adolescent_girls_11_14_all_v2) as cases_person_adolescent_girls_11_14_all_v2
    FROM "agg_awc_2019-04-01_4"
    WHERE supervisor_is_test<>1
    GROUP BY block_id
)ut
where agg_awc.block_id=ut.block_id;


UPDATE "agg_awc_2019-04-01_2" agg_awc
    set cases_person_adolescent_girls_11_14_out_of_school = ut.girls_out_of_schoool,
    cases_person_adolescent_girls_11_14_all_v2 = ut.cases_person_adolescent_girls_11_14_all_v2
FROM (
    select
    district_id,
    sum(cases_person_adolescent_girls_11_14_out_of_school) as girls_out_of_schoool,
    sum(cases_person_adolescent_girls_11_14_all_v2) as cases_person_adolescent_girls_11_14_all_v2
    FROM "agg_awc_2019-04-01_3"
    WHERE block_is_test<>1
    GROUP BY district_id
)ut
where agg_awc.district_id=ut.district_id;


UPDATE "agg_awc_2019-04-01_1" agg_awc
    set cases_person_adolescent_girls_11_14_out_of_school = ut.girls_out_of_schoool,
    cases_person_adolescent_girls_11_14_all_v2 = ut.cases_person_adolescent_girls_11_14_all_v2
FROM (
    select
    state_id,
    sum(cases_person_adolescent_girls_11_14_out_of_school) as girls_out_of_schoool,
    sum(cases_person_adolescent_girls_11_14_all_v2) as cases_person_adolescent_girls_11_14_all_v2
    FROM "agg_awc_2019-04-01_2"
    WHERE district_is_test<>1
    GROUP BY state_id
)ut
where agg_awc.state_id=ut.state_id;







