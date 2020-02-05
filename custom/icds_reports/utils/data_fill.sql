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
