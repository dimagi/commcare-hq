UPDATE "agg_awc_2019-07-01_5" agg_awc SET
    thr_eligible_child = thr_eligible,
    thr_rations_21_plus_distributed_child = rations_21_plus_distributed
FROM (
    SELECT
        awc_id,
        month,
        sum(thr_eligible) as thr_eligible,
        sum(rations_21_plus_distributed) as rations_21_plus_distributed
    FROM agg_child_health
    WHERE month ='2019-07-01' AND aggregation_level = 5 GROUP BY awc_id, month
) ut
WHERE ut.month = agg_awc.month AND ut.awc_id = agg_awc.awc_id;



UPDATE "agg_awc_2019-07-01_4" agg_awc
SET
thr_eligible_child = ut.thr_eligible_child,
thr_rations_21_plus_distributed_child = ut.thr_rations_21_plus_distributed_child,

FROM (
    SELECT
    SUM(thr_eligible_child) as thr_eligible_child,
    SUM(thr_rations_21_plus_distributed_child) as thr_rations_21_plus_distributed_child,
    supervisor_id
    from "agg_awc_2019-07-01_5" where awc_is_test<>1
    group by supervisor_id
) ut
where ut.supervisor_id = agg_awc.supervisor_id;


UPDATE "agg_awc_2019-07-01_3" agg_awc
SET
thr_eligible_child = ut.thr_eligible_child,
thr_rations_21_plus_distributed_child = ut.thr_rations_21_plus_distributed_child,
FROM (
    SELECT
    SUM(thr_eligible_child) as thr_eligible_child,
    SUM(thr_rations_21_plus_distributed_child) as thr_rations_21_plus_distributed_child,
    block_id
    from "agg_awc_2019-07-01_4" where supervisor_is_test<>1
    group by block_id
) ut
where ut.block_id = agg_awc.block_id;


UPDATE "agg_awc_2019-07-01_2" agg_awc
SET
thr_eligible_child = ut.thr_eligible_child,
thr_rations_21_plus_distributed_child = ut.thr_rations_21_plus_distributed_child,
FROM (
    SELECT
    SUM(thr_eligible_child) as thr_eligible_child,
    SUM(thr_rations_21_plus_distributed_child) as thr_rations_21_plus_distributed_child,
    district_id
    from "agg_awc_2019-07-01_3" where block_is_test<>1
    group by district_id
) ut
where ut.district_id = agg_awc.district_id;


UPDATE "agg_awc_2019-07-01_1" agg_awc
SET
thr_eligible_child = ut.thr_eligible_child,
thr_rations_21_plus_distributed_child = ut.thr_rations_21_plus_distributed_child,
FROM (
    SELECT

    SUM(thr_eligible_child) as thr_eligible_child,
    SUM(thr_rations_21_plus_distributed_child) as thr_rations_21_plus_distributed_child,
    state_id
    from "agg_awc_2019-07-01_2" where district_is_test<>1
    group by state_id
) ut
where ut.state_id = agg_awc.state_id;

