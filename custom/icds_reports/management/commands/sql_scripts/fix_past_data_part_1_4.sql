UPDATE
  "agg_child_health_{start_date}" agg_child_health
SET
  lunch_count_21_days = ut.lunch_count_21_days
FROM
  (
    SELECT
      supervisor_id,
      gender,
      age_tranche,
      SUM(lunch_count_21_days) as lunch_count_21_days
    FROM
      "agg_child_health_{start_date}" agg_child
      INNER JOIN (
        SELECT
          DISTINCT ucr.doc_id
        FROM
          "awc_location_local" ucr
        WHERE
          ucr.awc_is_test = 0
          AND aggregation_level = 5
      ) tt ON tt.doc_id = agg_child.awc_id
    WHERE agg_child.aggregation_level=5
    GROUP BY
      state_id,
      district_id,
      block_id,
      supervisor_id,
      gender,
      age_tranche
  ) ut
WHERE
  agg_child_health.supervisor_id = ut.supervisor_id
  AND agg_child_health.gender = ut.gender
  AND agg_child_health.age_tranche = ut.age_tranche
  AND agg_child_health.aggregation_level=4;
