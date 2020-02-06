UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-11-01'
/*
 EXPLAIN UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-11-01';
                                                                                                  QUERY PLAN
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
   Task Count: 64
   Tasks Shown: One of 64
   ->  Task
         Node: host=100.71.184.232 port=6432 dbname=icds_ucr
         ->  Update on child_health_monthly_323196 child_health_monthly  (cost=0.56..567978.61 rows=2524 width=565)
               Update on child_health_monthly_default_102648 child_health_monthly_1
               ->  Nested Loop  (cost=0.56..567978.61 rows=2524 width=565)
                     ->  Index Scan using chm_month_supervisor_id_default_102648 on child_health_monthly_default_102648 child_health_monthly_1  (cost=0.56..432139.38 rows=654224 width=555)
                           Index Cond: (month = '2019-11-01'::date)
                     ->  Index Scan using "ix_ucr_icds-cas_static-child_health_cases_a46c129f_4380d_103418" on "ucr_icds-cas_static-child_health_cases_a46c129f_103418" ut  (cost=0.00..0.20 rows=1 width=84)
                           Index Cond: (doc_id = child_health_monthly_1.case_id)
                           Filter: (child_health_monthly_1.supervisor_id = supervisor_id)
(13 rows)
(28 rows)
 */



UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-10-01';



UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-09-01';


UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-08-01';


UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-07-01';



UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-06-01';



UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-05-01';


UPDATE child_health_monthly
set opened_on = ut.opened_on
FROM "ucr_icds-cas_static-child_health_cases_a46c129f" ut
where ut.doc_id=child_health_monthly.case_id and child_health_monthly.supervisor_id=ut.supervisor_id and month='2019-06-01';
