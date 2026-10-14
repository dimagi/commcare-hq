UPDATE child_health_monthly
    set num_rations_distributed = CASE WHEN thr_eligible=1 THEN COALESCE(thr.days_ration_given_child, 0) ELSE NULL END,
        days_ration_given_child = thr.days_ration_given_child
FROM (
    SELECT DISTINCT ON (child_health_case_id)
            LAST_VALUE(supervisor_id) over w AS supervisor_id,
            '2020-01-01'::date AS month,
            child_health_case_id AS case_id,
            MAX(timeend) over w AS latest_time_end_processed,
            CASE WHEN SUM(days_ration_given_child) over w > 32767 THEN 32767 ELSE SUM(days_ration_given_child) over w END AS days_ration_given_child
          FROM "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea"
          WHERE timeend >= '2020-01-01' AND timeend < '2020-02-01' AND
                child_health_case_id IS NOT NULL
    WINDOW w AS (PARTITION BY supervisor_id, child_health_case_id)
    ) thr
where
    child_health_monthly.month = thr.month AND
    child_health_monthly.case_id = thr.case_id AND
    child_health_monthly.supervisor_id = thr.supervisor_id AND
    child_health_monthly.month = '2020-01-01';
/*
 Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
   ->  Distributed Subplan 412_1
         ->  Unique  (cost=0.00..0.00 rows=0 width=0)
               ->  Sort  (cost=0.00..0.00 rows=0 width=0)
                     Sort Key: remote_scan.case_id
                     ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
                           Task Count: 64
                           Tasks Shown: One of 64
                           ->  Task
                                 Node: host=100.71.184.232 port=6432 dbname=icds_ucr
                                 ->  Unique  (cost=512543.28..514196.39 rows=123872 width=122)
                                       ->  Sort  (cost=512543.28..513369.84 rows=330622 width=122)
                                             Sort Key: "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea".child_health_case_id
                                             ->  WindowAgg  (cost=447988.20..457080.30 rows=330622 width=122)
                                                   ->  Sort  (cost=447988.20..448814.75 rows=330622 width=80)
                                                         Sort Key: "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea".supervisor_id, "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea".child_health_case_id
                                                         ->  Gather  (cost=1000.00..400466.92 rows=330622 width=80)
                                                               Workers Planned: 6
                                                               ->  Parallel Seq Scan on "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea_104058" "ucr_icds-cas_static-dashboard_thr_forms_b8bca6ea"  (cost=0.00..366404.72 rows=55104 width=80)
                                                                     Filter: ((child_health_case_id IS NOT NULL) AND (timeend >= '2020-01-01 00:00:00'::timestamp without time zone) AND (timeend < '2020-02-01 00:00:00'::timestamp without time zone))
   Task Count: 64
   Tasks Shown: One of 64
   ->  Task
         Node: host=100.71.184.232 port=6432 dbname=icds_ucr
         ->  Update on child_health_monthly_323196 child_health_monthly  (cost=0.43..25.80 rows=1 width=740)
               Update on "child_health_monthly_2020-01-01_403772" child_health_monthly_1
               ->  Nested Loop  (cost=0.43..25.80 rows=1 width=740)
                     ->  Function Scan on read_intermediate_result intermediate_result  (cost=0.00..12.50 rows=5 width=176)
                           Filter: (month = '2020-01-01'::date)
                     ->  Index Scan using "child_health_monthly_2020-01-01_403772_case_id_idx" on "child_health_monthly_2020-01-01_403772" child_health_monthly_1  (cost=0.42..2.65 rows=1 width=634)
                           Index Cond: (case_id = intermediate_result.case_id)
                           Filter: ((month = '2020-01-01'::date) AND (intermediate_result.supervisor_id = supervisor_id))
(32 rows)
*/


DROP TABLE IF EXISTS temp_agg_child_health_rhit;
CREATE UNLOGGED TABLE temp_agg_child_health_rhit AS (select state_id,supervisor_id,awc_id,month,gender,age_tranche,caste,disabled,minority,resident, rations_21_plus_distributed, days_ration_given_child from agg_child_health where 1=0);
SELECT create_distributed_table('temp_agg_child_health_rhit', 'supervisor_id');
INSERT INTO temp_agg_child_health_rhit(
state_id,
        supervisor_id,
        awc_id,
        month,
        gender,
        age_tranche,
        caste,
        disabled,
        minority,
        resident,
        rations_21_plus_distributed,
        days_ration_given_child
)
(
    select
        state_id,
        supervisor_id,
        awc_id,
        month,
        sex,
        age_tranche,
        caste,
        COALESCE(chm.disabled, 'no') as coalesce_disabled,
        COALESCE(chm.minority, 'no') as coalesce_minority,
        COALESCE(chm.resident, 'no') as coalesce_resident,
        SUM(CASE WHEN chm.num_rations_distributed >= 21 THEN 1 ELSE 0 END) as rations_21_plus_distributed,
        SUM(chm.days_ration_given_child) as days_ration_given_child
    from child_health_monthly chm
        WHERE month = '2020-01-01'
    group by  state_id,
        supervisor_id,
        awc_id,
        month,
        sex,
        age_tranche,
        caste,
        coalesce_disabled,
        coalesce_minority,
        coalesce_resident
);


DROP TABLE IF EXISTS temp_agg_child;
CREATE UNLOGGED TABLE temp_agg_child AS (select * from temp_agg_child_health_rhit);
UPDATE agg_child_health
    SET
        rations_21_plus_distributed = thr_temp.rations_21_plus_distributed,
        days_ration_given_child = thr_temp.days_ration_given_child

from temp_agg_child thr_temp
where
    agg_child_health.state_id = thr_temp.state_id AND
    agg_child_health.supervisor_id = thr_temp.supervisor_id AND
    agg_child_health.awc_id = thr_temp.awc_id AND
    agg_child_health.month = thr_temp.month AND
    agg_child_health.gender = thr_temp.gender AND
    agg_child_health.age_tranche = thr_temp.age_tranche AND
    agg_child_health.caste = thr_temp.caste AND
    agg_child_health.disabled = thr_temp.disabled AND
    agg_child_health.minority = thr_temp.minority AND
    agg_child_health.resident = thr_temp.resident AND
    agg_child_health.aggregation_level = 5 AND
    agg_child_health.month='2020-01-01';


UPDATE agg_child_health
    SET
        rations_21_plus_distributed = ut.rations_21_plus_distributed,
        days_ration_given_child = ut.days_ration_given_child
from (
    SELECT
        month,
        supervisor_id,
        gender,
        age_tranche,
        sum(rations_21_plus_distributed) as rations_21_plus_distributed,
        sum(days_ration_given_child) as days_ration_given_child
    from agg_child_health
        WHERE aggregation_level=5 AND month = '2020-01-01' GROUP BY month, supervisor_id, gender, age_tranche
) ut
    WHERE
        agg_child_health.month=ut.month AND
        agg_child_health.supervisor_id=ut.supervisor_id AND
        agg_child_health.gender=ut.gender AND
        agg_child_health.age_tranche=ut.age_tranche AND
        agg_child_health.aggregation_level=4 AND
        agg_child_health.month = '2020-01-01'


UPDATE agg_child_health
    SET
        rations_21_plus_distributed = ut.rations_21_plus_distributed,
        days_ration_given_child = ut.days_ration_given_child
from (
    SELECT
        month,
        block_id,
        gender,
        age_tranche,
        sum(rations_21_plus_distributed) as rations_21_plus_distributed,
        sum(days_ration_given_child) as days_ration_given_child
    from agg_child_health
        WHERE aggregation_level=4 AND month = '2020-01-01' GROUP BY month, block_id, gender, age_tranche
) ut
    WHERE
        agg_child_health.month=ut.month AND
        agg_child_health.block_id=ut.block_id AND
        agg_child_health.gender=ut.gender AND
        agg_child_health.age_tranche=ut.age_tranche AND
        agg_child_health.aggregation_level=3 AND
        agg_child_health.month = '2020-01-01';


UPDATE agg_child_health
    SET
        rations_21_plus_distributed = ut.rations_21_plus_distributed,
        days_ration_given_child = ut.days_ration_given_child
from (
    SELECT
        month,
        district_id,
        gender,
        age_tranche,
        sum(rations_21_plus_distributed) as rations_21_plus_distributed,
        sum(days_ration_given_child) as days_ration_given_child
    from agg_child_health
        WHERE aggregation_level=3 AND month = '2020-01-01' GROUP BY month, district_id, gender, age_tranche
) ut
    WHERE
        agg_child_health.month=ut.month AND
        agg_child_health.district_id=ut.district_id AND
        agg_child_health.gender=ut.gender AND
        agg_child_health.age_tranche=ut.age_tranche AND
        agg_child_health.aggregation_level=2;


UPDATE agg_child_health
    SET
        rations_21_plus_distributed = ut.rations_21_plus_distributed,
        days_ration_given_child = ut.days_ration_given_child
from (
    SELECT
        month,
        state_id,
        gender,
        age_tranche,
        sum(rations_21_plus_distributed) as rations_21_plus_distributed,
        sum(days_ration_given_child) as days_ration_given_child
    from agg_child_health
        WHERE aggregation_level=2 AND month = '2020-01-01' GROUP BY month, state_id, gender, age_tranche
) ut
    WHERE
        agg_child_health.month=ut.month AND
        agg_child_health.state_id=ut.state_id AND
        agg_child_health.gender=ut.gender AND
        agg_child_health.age_tranche=ut.age_tranche AND
        agg_child_health.aggregation_level=1;
