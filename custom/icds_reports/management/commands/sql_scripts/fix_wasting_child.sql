UPDATE child_health_monthly
    SET current_month_wasting = 'unmeasured'

where
    child_health_monthly.height_measured_in_month <> 1 AND
    child_health_monthly.current_month_wasting is distinct FROM NULL AND
    child_health_monthly.month = '2020-01-01';
/*
 Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
   Task Count: 64
   Tasks Shown: One of 64
   ->  Task
         Node: host=100.71.184.232 port=6432 dbname=icds_ucr
         ->  Update on child_health_monthly_323196 child_health_monthly  (cost=0.00..73224.14 rows=435930 width=663)
               Update on "child_health_monthly_2020-01-01_403772" child_health_monthly_1
               ->  Seq Scan on "child_health_monthly_2020-01-01_403772" child_health_monthly_1  (cost=0.00..73224.14 rows=435930 width=663)
                     Filter: ((current_month_wasting IS NOT NULL) AND (height_measured_in_month <> 1) AND (month = '2020-01-01'::date))
(9 rows)

*/


DROP TABLE IF EXISTS temp_agg_child_health_rhit;
CREATE UNLOGGED TABLE temp_agg_child_health_rhit AS (select state_id,supervisor_id,awc_id,month,gender,age_tranche,caste,disabled,minority,resident, wasting_moderate, wasting_severe, wasting_normal from agg_child_health where 1=0);
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
        wasting_moderate,
        wasting_severe,
        wasting_normal
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
        SUM(CASE WHEN chm.current_month_wasting = 'moderate' THEN 1 ELSE 0 END) AS wasting_moderate,
        SUM(CASE WHEN chm.current_month_wasting = 'severe' THEN 1 ELSE 0 END) AS wasting_severe,
        SUM(CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END) AS wasting_normal
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
        wasting_moderate = thr_temp.wasting_moderate,
        wasting_severe = thr_temp.wasting_severe,
        wasting_normal = thr_temp.wasting_normal

from temp_agg_child wasting_temp
where
    agg_child_health.state_id = wasting_temp.state_id AND
    agg_child_health.supervisor_id = wasting_temp.supervisor_id AND
    agg_child_health.awc_id = wasting_temp.awc_id AND
    agg_child_health.month = wasting_temp.month AND
    agg_child_health.gender = wasting_temp.sex AND
    agg_child_health.age_tranche = wasting_temp.age_tranche AND
    agg_child_health.caste = wasting_temp.caste AND
    agg_child_health.disabled = wasting_temp.coalesce_disabled AND
    agg_child_health.minority = wasting_temp.coalesce_minority AND
    agg_child_health.resident = wasting_temp.coalesce_resident AND
    agg_child_health.aggregation_level = 5;


UPDATE agg_child_health
    SET
        wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        wasting_normal = ut.wasting_normal
from (
    SELECT
        month,
        supervisor_id,
        gender,
        age_tranche,
        sum(wasting_moderate) as wasting_moderate,
        sum(wasting_severe) as wasting_severe,
        sum(wasting_normal) as wasting_normal
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
        wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        wasting_normal = ut.wasting_normal
from (
    SELECT
        month,
        block_id,
        gender,
        age_tranche,
        sum(wasting_moderate) as wasting_moderate,
        sum(wasting_severe) as wasting_severe,
        sum(wasting_normal) as wasting_normal
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
        wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        wasting_normal = ut.wasting_normal
from (
    SELECT
        month,
        district_id,
        gender,
        age_tranche,
        sum(wasting_moderate) as wasting_moderate,
        sum(wasting_severe) as wasting_severe,
        sum(wasting_normal) as wasting_normal
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
        wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        wasting_normal = ut.wasting_normal
from (
    SELECT
        month,
        state_id,
        gender,
        age_tranche,
        sum(wasting_moderate) as wasting_moderate,
        sum(wasting_severe) as wasting_severe,
        sum(wasting_normal) as wasting_normal
    from agg_child_health
        WHERE aggregation_level=2 AND month = '2020-01-01' GROUP BY month, state_id, gender, age_tranche
) ut
    WHERE
        agg_child_health.month=ut.month AND
        agg_child_health.state_id=ut.state_id AND
        agg_child_health.gender=ut.gender AND
        agg_child_health.age_tranche=ut.age_tranche AND
        agg_child_health.aggregation_level=1;
