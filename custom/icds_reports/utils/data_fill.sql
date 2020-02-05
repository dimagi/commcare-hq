UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-11-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-11-01';
/*
 Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
   ->  Distributed Subplan 46_1
         ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
               Task Count: 64
               Tasks Shown: One of 64
               ->  Task
                     Node: host=100.71.184.232 port=6432 dbname=icds_ucr
                     ->  Gather  (cost=1000.56..503939.95 rows=715391 width=49)
                           Workers Planned: 8
                           ->  Nested Loop Left Join  (cost=0.56..431400.85 rows=89424 width=49)
                                 ->  Parallel Append  (cost=0.56..414192.34 rows=89424 width=74)
                                       ->  Parallel Index Only Scan using child_health_monthly_pkey_102648 on child_health_monthly_default_102648 child_health_monthly  (cost=0.56..413745.22 rows=89424 width=74)
                                             Index Cond: (month = '2019-11-01'::date)
                                 ->  Index Scan using "ix_ucr_icds-cas_static-child_health_cases_a46c129f_4380d_103418" on "ucr_icds-cas_static-child_health_cases_a46c129f_103418" child_ucr  (cost=0.00..0.18 rows=1 width=78)
                                       Index Cond: (child_health_monthly.case_id = doc_id)
                                       Filter: (child_health_monthly.supervisor_id = supervisor_id)
   Task Count: 64
   Tasks Shown: One of 64
   ->  Task
         Node: host=100.71.184.232 port=6432 dbname=icds_ucr
         ->  Update on child_health_monthly_323196 child_health_monthly  (cost=0.56..116.07 rows=6 width=627)
               Update on child_health_monthly_default_102648 child_health_monthly_1
               ->  Nested Loop  (cost=0.56..116.07 rows=6 width=627)
                     ->  Function Scan on read_intermediate_result intermediate_result  (cost=0.00..12.50 rows=5 width=112)
                           Filter: (month = '2019-11-01'::date)
                     ->  Index Scan using chm_case_idx_102648 on child_health_monthly_default_102648 child_health_monthly_1  (cost=0.56..20.70 rows=1 width=555)
                           Index Cond: (case_id = intermediate_result.doc_id)
                           Filter: (month = '2019-11-01'::date)
(28 rows)
 */


UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-10-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-10-01';



UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-09-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-09-01';


UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-08-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-08-01';




UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-07-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-07-01';


UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-06-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-06-01';



UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-05-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-05-01';


UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM (
    select
    child_ucr.opened_on,
    child_ucr.doc_id,
    child_health_monthly.month
    from child_health_monthly left join "ucr_icds-cas_static-child_health_cases_a46c129f" child_ucr on child_health_monthly.case_id = child_ucr.doc_id
    AND child_health_monthly.supervisor_id=child_ucr.supervisor_id
    where child_health_monthly.month='2019-04-01'
) ut
where ut.doc_id = child_health_monthly.case_id and ut.month=child_health_monthly.month and child_health_monthly.month='2019-04-01';
