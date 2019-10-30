-- CHILD HEALTH MONTHLY 
UPDATE "child_health_monthly" SET
fully_immunized_eligible = 0,
fully_immunized_on_time = 0,
fully_immunized_late = 0

where fully_immunized_eligible = 1 and age_tranche::integer<=12 and month='2019-07-01';



-- AGG CHILD HEALTH
UPDATE "agg_child_health_2019-07-01_5" agg_child SET
fully_immunized_eligible = ut.fully_immunized_eligible,
fully_immunized_on_time = ut.fully_immunized_on_time,
fully_immunized_late = ut.fully_immunized_late
FROM (
    SELECT
        SUM(fully_immunized_eligible) as fully_immunized_eligible,
        SUM(fully_immunized_on_time) as fully_immunized_on_time,
        SUM(fully_immunized_late) as fully_immunized_late,
        COALESCE(chm.disabled, 'no') as coalesce_disabled,
        COALESCE(chm.minority, 'no') as coalesce_minority,
        COALESCE(chm.resident, 'no') as coalesce_resident,
        awc_id, sex, age_tranche, caste, coalesce_disabled, coalesce_minority, coalesce_resident
    FROM child_health_monthly
    WHERE month='2019-07-01'
    GROUP BY awc_id
) ut
WHERE (
    agg_child.awc_id = ut.awc_id AND
    agg_child.gender = ut.sex AND
    agg_child.age_tranche = ut.age_tranche AND
    agg_child.caste = ut.caste AND
    agg_child.coalesce_disabled = ut.coalesce_disabled AND
    agg_child.coalesce_minority = ut.coalesce_minority AND
    agg_child.coalesce_resident = ut.coalesce_resident
)



-- ROLL UPS
UPDATE "agg_child_health_2019-07-01_4" agg_child SET
fully_immunized_eligible = ut.fully_immunized_eligible,
fully_immunized_on_time = ut.fully_immunized_on_time,
fully_immunized_late = ut.fully_immunized_late
FROM (
    SELECT
        SUM(fully_immunized_eligible) as fully_immunized_eligible,
        SUM(fully_immunized_on_time) as fully_immunized_on_time,
        SUM(fully_immunized_late) as fully_immunized_late,
        supervisor_id, gender, age_tranche
    FROM "agg_child_health_2019-07-01_5"
    WHERE awc_is_test<>1
    GROUP BY supervisor_id, gender, age_tranche
) ut
WHERE (
    agg_child.supervisor_id = ut.supervisor_id AND
    agg_child.gender = ut.gender AND
    agg_child.age_tranche = ut.age_tranche
)


UPDATE "agg_child_health_2019-07-01_3" agg_child SET
fully_immunized_eligible = ut.fully_immunized_eligible,
fully_immunized_on_time = ut.fully_immunized_on_time,
fully_immunized_late = ut.fully_immunized_late
FROM (
    SELECT
        SUM(fully_immunized_eligible) as fully_immunized_eligible,
        SUM(fully_immunized_on_time) as fully_immunized_on_time,
        SUM(fully_immunized_late) as fully_immunized_late,
        block_id, gender, age_tranche
    FROM "agg_child_health_2019-07-01_4"
    WHERE supervisor_is_test<>1
    GROUP BY block_id, gender, age_tranche
) ut
WHERE (
    agg_child.block_id = ut.block_id AND
    agg_child.gender = ut.gender AND
    agg_child.age_tranche = ut.age_tranche
)


UPDATE "agg_child_health_2019-07-01_2" agg_child SET
fully_immunized_eligible = ut.fully_immunized_eligible,
fully_immunized_on_time = ut.fully_immunized_on_time,
fully_immunized_late = ut.fully_immunized_late
FROM (
    SELECT
        SUM(fully_immunized_eligible) as fully_immunized_eligible,
        SUM(fully_immunized_on_time) as fully_immunized_on_time,
        SUM(fully_immunized_late) as fully_immunized_late,
        district_id, gender, age_tranche
    FROM "agg_child_health_2019-07-01_3"
    WHERE block_is_test<>1
    GROUP BY district_id, gender, age_tranche
) ut
WHERE (
    agg_child.district_id = ut.district_id AND
    agg_child.gender = ut.gender AND
    agg_child.age_tranche = ut.age_tranche
)


UPDATE "agg_child_health_2019-07-01_1" agg_child SET
fully_immunized_eligible = ut.fully_immunized_eligible,
fully_immunized_on_time = ut.fully_immunized_on_time,
fully_immunized_late = ut.fully_immunized_late
FROM (
    SELECT
        SUM(fully_immunized_eligible) as fully_immunized_eligible,
        SUM(fully_immunized_on_time) as fully_immunized_on_time,
        SUM(fully_immunized_late) as fully_immunized_late,
        state_id, gender, age_tranche
    FROM "agg_child_health_2019-07-01_2"
    WHERE district_is_test<>1
    GROUP BY state_id, gender, age_tranche
) ut
WHERE (
    agg_child.state_id = ut.state_id AND
    agg_child.gender = ut.gender AND
    agg_child.age_tranche = ut.age_tranche
)