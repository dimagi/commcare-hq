UPDATE
  "agg_child_health_{start_date}" agg_child_health
SET
  lunch_count_21_days = ut.lunch_count_21_days
FROM
  (
    SELECT
      state_id,
      gender,
      age_tranche,
      SUM(lunch_count_21_days) as lunch_count_21_days
    FROM
      "agg_child_health_{start_date}" agg_child
      INNER JOIN (
        SELECT
          DISTINCT ucr.district_id
        FROM
          "awc_location_local" ucr
        WHERE
          ucr.district_is_test = 0
          AND aggregation_level = 2
      ) tt ON tt.district_id = agg_child.district_id
    WHERE agg_child.aggregation_level=2
    GROUP BY
      state_id,
      gender,
      age_tranche
  ) ut
WHERE
  agg_child_health.state_id = ut.state_id
  AND agg_child_health.gender = ut.gender
  AND agg_child_health.age_tranche = ut.age_tranche
  AND agg_child_health.aggregation_level=1;
