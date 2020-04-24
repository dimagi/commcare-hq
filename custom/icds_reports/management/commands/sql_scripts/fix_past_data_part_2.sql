DROP TABLE IF EXISTS temp_chm;
CREATE UNLOGGED TABLE temp_chm (LIKE agg_child_health);
SELECT create_distributed_table('temp_chm', 'supervisor_id');
INSERT INTO "temp_chm" (
  awc_id, supervisor_id, month, sex, age_tranche, caste,
  wasting_moderate, wasting_severe, wasting_normal, stunting_moderate, stunting_severe,
  stunting_normal, weighed_and_height_measured_in_month, coalesce_disabled, coalesce_minority, coalesce_resident
) (
  SELECT
      awc_id, supervisor_id, chm.month, sex, age_tranche, caste,
      SUM(
        CASE WHEN chm.current_month_wasting = 'moderate' THEN 1 ELSE 0 END
      ) as wasting_moderate,
      SUM(
        CASE WHEN chm.current_month_wasting = 'severe' THEN 1 ELSE 0 END
      ) as wasting_severe,
      SUM(
        CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END
      ) as wasting_normal,
      SUM(
        CASE WHEN chm.current_month_stunting = 'moderate' THEN 1 ELSE 0 END
      ) as stunting_moderate,
      SUM(
        CASE WHEN chm.current_month_stunting = 'severe' THEN 1 ELSE 0 END
      ) as stunting_severe,
      SUM(
        CASE WHEN chm.current_month_stunting = 'normal' THEN 1 ELSE 0 END
      ) as stunting_normal,
      SUM(chm.height_measured_in_month) as height_measured_in_month,
      SUM(
        CASE WHEN chm.nutrition_status_weighed = 1
        AND chm.height_measured_in_month = 1 THEN 1 ELSE 0 END
      ) as weighed_and_height_measured_in_month,
      COALESCE(chm.disabled, 'no') as coalesce_disabled,
      COALESCE(chm.minority, 'no') as coalesce_minority,
      COALESCE(chm.resident, 'no') as coalesce_resident
    FROM
      "child_health_monthly" chm
    WHERE
      chm.month = '{start_date}'
    GROUP BY
      chm.awc_id,
      chm.supervisor_id,
      chm.month,
      chm.sex,
      chm.age_tranche,
      chm.caste,
      coalesce_disabled,
      coalesce_minority,
      coalesce_resident
);
DROP TABLE IF EXISTS temp_chm_local;
CREATE temp_chm_local TABLE AS SELECT * from temp_chm;


--    QUERY PLAN
-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Sort  (cost=0.00..0.00 rows=0 width=0)
--    Sort Key: remote_scan.awc_id
--    ->  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--          Group Key: remote_scan.awc_id, remote_scan.supervisor_id, remote_scan.month, remote_scan.sex, remote_scan.age_tranche, remote_scan.caste, remote_scan.coalesce_disabled, remote_scan.coalesce_minority, remote_scan.coalesce_resident
--          ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--                Task Count: 64
--                Tasks Shown: One of 64
--                ->  Task
--                      Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                      ->  Finalize GroupAggregate  (cost=63668.83..67899.15 rows=5961 width=238)
--                            Group Key: chm.awc_id, chm.supervisor_id, chm.month, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
--                            ->  Gather Merge  (cost=63668.83..67079.51 rows=17883 width=238)
--                                  Workers Planned: 3
--                                  ->  Partial GroupAggregate  (cost=62668.79..63978.22 rows=5961 width=238)
--                                        Group Key: chm.awc_id, chm.supervisor_id, chm.month, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
--                                        ->  Sort  (cost=62668.79..62716.86 rows=19228 width=200)
--                                              Sort Key: chm.awc_id, chm.supervisor_id, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
--                                              ->  Parallel Append  (cost=0.56..60222.33 rows=19228 width=200)
--                                                    ->  Parallel Index Scan using chm_month_supervisor_id_default_102648 on child_health_monthly_default_102648 chm  (cost=0.56..60126.19 rows=19228 width=200)
--                                                          Index Cond: (month = '2017-03-01'::date)
