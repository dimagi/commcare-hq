INSERT INTO "icds_dashboard_growth_monitoring_forms" (
	case_id, state_id, supervisor_id, month,
            weight_child, weight_child_last_recorded,
            height_child, height_child_last_recorded,
            zscore_grading_wfa, zscore_grading_wfa_last_recorded,
            zscore_grading_hfa, zscore_grading_hfa_last_recorded,
            zscore_grading_wfh, zscore_grading_wfh_last_recorded,
            muac_grading, muac_grading_last_recorded,  latest_time_end_processed
    )(SELECT DISTINCT child_health_case_id AS case_id,
                state_id As state_id,
                supervisor_id AS supervisor_id,
                '2018-05-01'::DATE AS month,
                LAST_VALUE(weight_child) OVER weight_child AS weight_child,
                CASE
                    WHEN LAST_VALUE(weight_child) OVER weight_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER weight_child
                END AS weight_child_last_recorded,
                LAST_VALUE(height_child) OVER height_child AS height_child,
                CASE
                    WHEN LAST_VALUE(height_child) OVER height_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER height_child
                END AS height_child_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa
                END AS zscore_grading_wfa,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfa
                END AS zscore_grading_wfa_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa
                END AS zscore_grading_hfa,
                CASE
                    WHEN LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_hfa
                END AS zscore_grading_hfa_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh
                END AS zscore_grading_wfh,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfh
                END AS zscore_grading_wfh_last_recorded,
                CASE
                    WHEN LAST_VALUE(muac_grading) OVER muac_grading = 0 THEN NULL
                    ELSE LAST_VALUE(muac_grading) OVER muac_grading
                END AS muac_grading,
                CASE
                    WHEN LAST_VALUE(muac_grading) OVER muac_grading = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER muac_grading
                END AS muac_grading_last_recorded,
                GREATEST(
                    CASE
                    WHEN LAST_VALUE(weight_child) OVER weight_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER weight_child END,
                    CASE
                    WHEN LAST_VALUE(height_child) OVER height_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER height_child END,
                    CASE
                    WHEN LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfa END,
                    CASE
                    WHEN LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_hfa END,
                    CASE
                    WHEN LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfh END,
                    CASE
                    WHEN LAST_VALUE(muac_grading) OVER muac_grading = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER muac_grading END,
                    '1970-01-01'
                ) AS latest_time_end_processed
            FROM "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625"
            WHERE  timeend < '2018-06-01' AND child_health_case_id IS NOT NULL
            WINDOW
                weight_child AS (
                    PARTITION BY supervisor_id, child_health_case_id
                    ORDER BY
                        CASE WHEN weight_child IS NULL THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                height_child AS (
                    PARTITION BY supervisor_id, child_health_case_id
                    ORDER BY
                        CASE WHEN height_child IS NULL THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_wfa AS (
                    PARTITION BY supervisor_id, child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_wfa = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_hfa AS (
                    PARTITION BY supervisor_id, child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_hfa = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_wfh AS (
                    PARTITION BY supervisor_id, child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_wfh = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                muac_grading AS (
                    PARTITION BY supervisor_id, child_health_case_id
                    ORDER BY
                        CASE WHEN muac_grading = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ))

--       QUERY PLAN
-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Insert on icds_dashboard_growth_monitoring_forms_102264 citus_table_alias  (cost=444108.23..444453.19 rows=4312 width=371)
--                ->  Subquery Scan on "*SELECT*"  (cost=444108.23..444453.19 rows=4312 width=371)
--                      ->  Unique  (cost=444108.23..444291.49 rows=4312 width=267)
--                            ->  Sort  (cost=444108.23..444119.01 rows=4312 width=267)
--                                  Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".state_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (GREATEST(CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::timestamp without time zone ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?) END, '1970-01-01 00:00:00'::timestamp without time zone)), (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::smallint ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) END), (CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::timestamp without time zone ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?) END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id
--                                  ->  WindowAgg  (cost=443546.08..443847.92 rows=4312 width=267)
--                                        ->  Sort  (cost=443546.08..443556.86 rows=4312 width=264)
--                                              Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                              ->  WindowAgg  (cost=443124.06..443285.76 rows=4312 width=264)
--                                                    ->  Sort  (cost=443124.06..443134.84 rows=4312 width=254)
--                                                          Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                          ->  WindowAgg  (cost=442702.04..442863.74 rows=4312 width=254)
--                                                                ->  Sort  (cost=442702.04..442712.82 rows=4312 width=244)
--                                                                      Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                      ->  WindowAgg  (cost=442280.02..442441.72 rows=4312 width=244)








-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- -------------------------------------------------------------------------------------------------------------------------------
-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Insert on icds_dashboard_growth_monitoring_forms_102264 citus_table_alias  (cost=444108.23..444453.19 rows=4312 width=371)
--                ->  Subquery Scan on "*SELECT*"  (cost=444108.23..444453.19 rows=4312 width=371)
--                      ->  Unique  (cost=444108.23..444291.49 rows=4312 width=267)
--                            ->  Sort  (cost=444108.23..444119.01 rows=4312 width=267)
--                                  Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".state_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (GREATEST(CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::timestamp without time zone ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?) END, '1970-01-01 00:00:00'::timestamp without time zone)), (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::smallint ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) END), (CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::timestamp without time zone ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?) END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id
--                                  ->  WindowAgg  (cost=443546.08..443847.92 rows=4312 width=267)
--                                        ->  Sort  (cost=443546.08..443556.86 rows=4312 width=264)
--                                              Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                              ->  WindowAgg  (cost=443124.06..443285.76 rows=4312 width=264)
--                                                    ->  Sort  (cost=443124.06..443134.84 rows=4312 width=254)
--                                                          Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                          ->  WindowAgg  (cost=442702.04..442863.74 rows=4312 width=254)
--                                                                ->  Sort  (cost=442702.04..442712.82 rows=4312 width=244)
--                                                                      Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                      ->  WindowAgg  (cost=442280.02..442441.72 rows=4312 width=244)
--                                                                            ->  Sort  (cost=442280.02..442290.80 rows=4312 width=234)
--                                                                                  Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                                  ->  WindowAgg  (cost=441858.00..442019.70 rows=4312 width=234)
--                                                                                        ->  Sort  (cost=441858.00..441868.78 rows=4312 width=194)
--                                                                                              Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child IS NULL) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                                              ->  WindowAgg  (cost=441435.98..441597.68 rows=4312 width=194)
--                                                                                                    ->  Sort  (cost=441435.98..441446.76 rows=4312 width=154)
--                                                                                                          Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child IS NULL) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                                                          ->  Seq Scan on "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625_103610" "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625"  (cost=0.00..441175.66 rows=4312 width=154)
--                                                                                                                Filter: ((child_health_case_id IS NOT NULL) AND (timeend < '2018-06-01 00:00:00'::timestamp without time zone) AND (worker_hash(supervisor_id) >= '-2147483648'::integer) AND (worker_hash(supervisor_id) <= '-2080374785'::integer))
-- (30 rows)



UPDATE child_health_monthly child_health
 SET
  zscore_grading_hfa = gm.zscore_grading_hfa,
  zscore_grading_hfa_recorded_in_month = CASE
			WHEN gm.zscore_grading_hfa_last_recorded>='2018-05-01' AND gm.zscore_grading_hfa_last_recorded<'2018-06-01' THEN 1
			ELSE 0
	END,
  zscore_grading_wfh = gm.zscore_grading_wfh,
	zscore_grading_wfh_recorded_in_month = CASE
			WHEN gm.zscore_grading_wfh_last_recorded>='2018-05-01' AND gm.zscore_grading_wfh_last_recorded<'2018-06-01' THEN 1
			ELSE 0
	END,
 	current_month_stunting = CASE
 			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
 			WHEN NOT (gm.zscore_grading_hfa_last_recorded BETWEEN '2018-05-01' AND '2018-05-31') THEN 'unmeasured'
 			WHEN gm.zscore_grading_hfa = 1 THEN 'severe'
 			WHEN gm.zscore_grading_hfa = 2 THEN 'moderate'
 			WHEN gm.zscore_grading_hfa = 3 THEN 'normal'
 		END,
 	stunting_last_recorded = CASE
			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
			WHEN gm.zscore_grading_hfa = 1 THEN 'severe'
			WHEN gm.zscore_grading_hfa = 2 THEN 'moderate'
			WHEN gm.zscore_grading_hfa = 3 THEN 'normal'
			ELSE 'unknown'
	END,
	wasting_last_recorded = CASE
			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
			WHEN gm.zscore_grading_wfh = 1 THEN 'severe'
			WHEN gm.zscore_grading_wfh = 2 THEN 'moderate'
			WHEN gm.zscore_grading_wfh = 3 THEN 'normal'
			ELSE 'unknown'
	END,
	current_month_wasting = CASE
			WHEN NOT (valid_in_month=1 AND age_tranche::Integer <= 60) THEN NULL
			WHEN NOT (gm.zscore_grading_wfh_last_recorded>='2018-05-01' AND gm.zscore_grading_wfh_last_recorded<'2018-06-01') THEN 'unmeasured'
			WHEN gm.zscore_grading_wfh = 1 THEN 'severe'
			WHEN gm.zscore_grading_wfh = 2 THEN 'moderate'
			WHEN gm.zscore_grading_wfh = 3 THEN 'normal'
			ELSE 'unmeasured'
	END
	FROM icds_dashboard_growth_monitoring_forms gm
	WHERE child_health.month=gm.month
		AND child_health.case_id=gm.case_id
		AND child_health.month='2018-05-01'
		AND gm.month='2018-05-01'
		AND child_health.supervisor_id=gm.supervisor_id;



-- -- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Update on child_health_monthly_323196 child_health  (cost=1.12..5.64 rows=1 width=661)
--                Update on child_health_monthly_default_102648 child_health_1
--                ->  Nested Loop  (cost=1.12..5.64 rows=1 width=661)
--                      ->  Index Scan using icds_dashboard_growth_mo_month_state_id_9dfbeda1_idx_102264 on icds_dashboard_growth_monitoring_forms_102264 gm  (cost=0.56..2.76 rows=1 width=100)
--                            Index Cond: (month = '2018-05-01'::date)
--                      ->  Index Scan using child_health_monthly_default_102648_pkey on child_health_monthly_default_102648 child_health_1  (cost=0.56..2.78 rows=1 width=519)
--                            Index Cond: ((supervisor_id = gm.supervisor_id) AND (case_id = (gm.case_id)::text) AND (month = '2018-05-01'::date))

DROP TABLE IF EXISTS temp_agg_child_my;
CREATE TABLE temp_agg_child_my AS
SELECT
	awc_id,
	supervisor_id,
	chm.month,
	sex,
	age_tranche,
	caste,
	SUM(CASE WHEN chm.current_month_wasting = 'moderate' THEN 1 ELSE 0 END) as wasting_moderate,
	SUM(CASE WHEN chm.current_month_wasting = 'severe' THEN 1 ELSE 0 END) as wasting_severe,
	SUM(CASE WHEN chm.current_month_stunting = 'moderate' THEN 1 ELSE 0 END) as stunting_moderate,
	SUM(CASE WHEN chm.current_month_stunting = 'severe' THEN 1 ELSE 0 END) as stunting_severe,
	SUM(CASE WHEN chm.current_month_wasting = 'normal' THEN 1 ELSE 0 END) as wasting_normal,
	SUM(CASE WHEN chm.current_month_stunting = 'normal' THEN 1 ELSE 0 END) as stunting_normal,
	SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 3 THEN 1 ELSE 0 END) as wasting_normal_v2,
	SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 2 THEN 1 ELSE 0 END) as wasting_moderate_v2,
	SUM(CASE WHEN chm.zscore_grading_wfh_recorded_in_month = 1 AND chm.zscore_grading_wfh = 1 THEN 1 ELSE 0 END) as wasting_severe_v2,
	SUM(CASE WHEN chm.zscore_grading_hfa_recorded_in_month = 1 AND chm.zscore_grading_hfa = 3 THEN 1 ELSE 0 END) as zscore_grading_hfa_normal,
	SUM(CASE WHEN chm.zscore_grading_hfa_recorded_in_month = 1 AND chm.zscore_grading_hfa = 2 THEN 1 ELSE 0 END) as zscore_grading_hfa_moderate,
	SUM(CASE WHEN chm.zscore_grading_hfa_recorded_in_month = 1 AND chm.zscore_grading_hfa = 1 THEN 1 ELSE 0 END) as zscore_grading_hfa_severe,
	SUM(chm.zscore_grading_hfa_recorded_in_month) as zscore_grading_hfa_recorded_in_month,
	SUM(chm.zscore_grading_wfh_recorded_in_month) as zscore_grading_wfh_recorded_in_month,
	COALESCE(chm.disabled, 'no') as coalesce_disabled,
	COALESCE(chm.minority, 'no') as coalesce_minority,
	COALESCE(chm.resident, 'no') as coalesce_resident

	FROM
	"child_health_monthly" chm
	WHERE chm.month='2018-05-01'
	GROUP BY chm.awc_id, chm.supervisor_id,
					 chm.month, chm.sex, chm.age_tranche, chm.caste,
					 coalesce_disabled, coalesce_minority, coalesce_resident
	ORDER BY chm.awc_id;

-- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Sort  (cost=0.00..0.00 rows=0 width=0)
--    Sort Key: remote_scan.awc_id
--    ->  HashAggregate  (cost=0.00..0.00 rows=0 width=0)
--          Group Key: remote_scan.awc_id, remote_scan.month, remote_scan.sex, remote_scan.age_tranche, remote_scan.caste, remote_scan.coalesce_disabled, remote_scan.coalesce_minority, remote_scan.coalesce_resident
--          ->  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--                Task Count: 64
--                Tasks Shown: One of 64
--                ->  Task
--                      Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--                      ->  Finalize GroupAggregate  (cost=159199.46..174986.20 rows=16230 width=253)
--                            Group Key: chm.awc_id, chm.month, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
--                            ->  Gather Merge  (cost=159199.46..171253.30 rows=64920 width=253)
--                                  Workers Planned: 4
--                                  ->  Partial GroupAggregate  (cost=158199.40..162520.64 rows=16230 width=253)
--                                        Group Key: chm.awc_id, chm.month, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
--                                        ->  Sort  (cost=158199.40..158300.84 rows=40575 width=167)
--                                              Sort Key: chm.awc_id, chm.sex, chm.age_tranche, chm.caste, (COALESCE(chm.disabled, 'no'::text)), (COALESCE(chm.minority, 'no'::text)), (COALESCE(chm.resident, 'no'::text))
--                                              ->  Parallel Append  (cost=0.56..153144.18 rows=40575 width=167)
--                                                    ->  Parallel Index Scan using chm_month_supervisor_id_default_102648 on child_health_monthly_default_102648 chm  (cost=0.56..152941.31 rows=40575 width=167)
--                                                          Index Cond: (month = '2018-05-01'::date)



UPDATE "agg_child_health_2018-05-01_5" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2,
        zscore_grading_hfa_normal = ut.zscore_grading_hfa_normal,
				zscore_grading_hfa_moderate = ut.zscore_grading_hfa_moderate,
				zscore_grading_hfa_severe = ut.zscore_grading_hfa_severe,
				zscore_grading_hfa_recorded_in_month = ut.zscore_grading_hfa_recorded_in_month,
				zscore_grading_wfh_recorded_in_month = ut.zscore_grading_wfh_recorded_in_month
    from temp_agg_Child_my ut 
    where (
        agg_child_health.awc_id=ut.awc_id and
        agg_child_health.supervisor_id=ut.supervisor_id and 
        agg_child_health.month=ut.month and
        agg_child_health.gender=ut.sex and
        agg_child_health.age_tranche=ut.age_tranche and
        agg_child_health.caste=ut.caste and
        agg_child_health.disabled=ut.coalesce_disabled and
        agg_child_health.minority = ut.coalesce_minority and
        agg_child_health.resident = ut.coalesce_resident
            );

Roll ups:

UPDATE "agg_child_health_2018-05-01_4" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2,
        zscore_grading_hfa_normal = ut.zscore_grading_hfa_normal,
				zscore_grading_hfa_moderate = ut.zscore_grading_hfa_moderate,
				zscore_grading_hfa_severe = ut.zscore_grading_hfa_severe,
				zscore_grading_hfa_recorded_in_month = ut.zscore_grading_hfa_recorded_in_month,
				zscore_grading_wfh_recorded_in_month = ut.zscore_grading_wfh_recorded_in_month
    from (
        SELECT
        supervisor_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2,
        SUM(zscore_grading_hfa_normal) as zscore_grading_hfa_normal,
				SUM(zscore_grading_hfa_moderate) as zscore_grading_hfa_moderate,
				SUM(zscore_grading_hfa_severe) as zscore_grading_hfa_severe,
				SUM(zscore_grading_hfa_recorded_in_month) as zscore_grading_hfa_recorded_in_month,
				SUM(zscore_grading_wfh_recorded_in_month) as zscore_grading_wfh_recorded_in_month

        FROM "agg_child_health_2018-05-01_5" agg_child INNER JOIN (SELECT DISTINCT ucr.doc_id FROM "awc_location_local" ucr WHERE ucr.awc_is_test=0 AND aggregation_level=5) tt ON tt.doc_id = agg_child.awc_id
        GROUP BY state_id, district_id,block_id,supervisor_id, gender, age_tranche
    ) ut 
    WHERE agg_child_health.supervisor_id = ut.supervisor_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;

-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2018-05-01_4" agg_child_health  (cost=2363343.53..2702061.45 rows=227 width=575)
--    ->  Hash Join  (cost=2363343.53..2702061.45 rows=227 width=575)
--          Hash Cond: ((ut.supervisor_id = agg_child_health.supervisor_id) AND (ut.gender = agg_child_health.gender) AND (ut.age_tranche = agg_child_health.age_tranche))
--          ->  Subquery Scan on ut  (cost=2348476.78..2598036.25 rows=457907 width=304)
--                ->  GroupAggregate  (cost=2348476.78..2593457.18 rows=457907 width=247)
--                      Group Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.supervisor_id, agg_child.gender, agg_child.age_tranche
--                      ->  Sort  (cost=2348476.78..2359924.46 rows=4579073 width=191)
--                            Sort Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.supervisor_id, agg_child.gender, agg_child.age_tranche
--                            ->  Hash Join  (cost=131129.17..851828.05 rows=4579073 width=191)
--                                  Hash Cond: (agg_child.awc_id = ucr.doc_id)
--                                  ->  Seq Scan on "agg_child_health_2018-05-01_5" agg_child  (cost=0.00..427238.73 rows=4579073 width=224)
--                                  ->  Hash  (cost=119279.11..119279.11 rows=612805 width=31)
--                                        ->  Unique  (cost=0.42..113151.06 rows=612805 width=31)
--                                              ->  Index Scan using awc_location_local_doc_id_idx on awc_location_local ucr  (cost=0.42..111331.32 rows=727897 width=31)
--                                                    Filter: ((awc_is_test = 0) AND (aggregation_level = 5))
--          ->  Hash  (cost=8827.09..8827.09 rows=93809 width=355)
--                ->  Seq Scan on "agg_child_health_2018-05-01_4" agg_child_health  (cost=0.00..8827.09 rows=93809 width=355)


UPDATE "agg_child_health_2018-05-01_3" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2,
        zscore_grading_hfa_normal = ut.zscore_grading_hfa_normal,
				zscore_grading_hfa_moderate = ut.zscore_grading_hfa_moderate,
				zscore_grading_hfa_severe = ut.zscore_grading_hfa_severe,
				zscore_grading_hfa_recorded_in_month = ut.zscore_grading_hfa_recorded_in_month,
				zscore_grading_wfh_recorded_in_month = ut.zscore_grading_wfh_recorded_in_month
    from (
        SELECT
        block_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2,
        SUM(zscore_grading_hfa_normal) as zscore_grading_hfa_normal,
				SUM(zscore_grading_hfa_moderate) as zscore_grading_hfa_moderate,
				SUM(zscore_grading_hfa_severe) as zscore_grading_hfa_severe,
				SUM(zscore_grading_hfa_recorded_in_month) as zscore_grading_hfa_recorded_in_month,
				SUM(zscore_grading_wfh_recorded_in_month) as zscore_grading_wfh_recorded_in_month

        FROM "agg_child_health_2018-05-01_4" agg_child INNER JOIN (SELECT DISTINCT ucr.supervisor_id FROM "awc_location_local" ucr WHERE ucr.supervisor_is_test=0 AND aggregation_level=4) tt ON tt.supervisor_id = agg_child.supervisor_id
        GROUP BY state_id, district_id,block_id, gender, age_tranche
    ) ut 
    WHERE agg_child_health.block_id = ut.block_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;

-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2018-05-01_3" agg_child_health  (cost=39211.48..46452.14 rows=5 width=546)
--    ->  Hash Join  (cost=39211.48..46452.14 rows=5 width=546)
--          Hash Cond: ((ut.block_id = agg_child_health.block_id) AND (ut.gender = agg_child_health.gender) AND (ut.age_tranche = agg_child_health.age_tranche))
--          ->  Subquery Scan on ut  (cost=37314.73..42192.80 rows=9381 width=304)
--                ->  GroupAggregate  (cost=37314.73..42098.99 rows=9381 width=214)
--                      Group Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.gender, agg_child.age_tranche
--                      ->  Sort  (cost=37314.73..37549.25 rows=93809 width=158)
--                            Sort Key: agg_child.state_id, agg_child.district_id, agg_child.block_id, agg_child.gender, agg_child.age_tranche
--                            ->  Hash Join  (cost=11851.10..20924.51 rows=93809 width=158)
--                                  Hash Cond: (agg_child.supervisor_id = ucr.supervisor_id)
--                                  ->  Seq Scan on "agg_child_health_2018-05-01_4" agg_child  (cost=0.00..8827.09 rows=93809 width=191)
--                                  ->  Hash  (cost=11641.04..11641.04 rows=16805 width=32)
--                                        ->  HashAggregate  (cost=11304.94..11472.99 rows=16805 width=32)
--                                              Group Key: ucr.supervisor_id
--                                              ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local ucr  (cost=0.42..11239.43 rows=26204 width=32)
--                                                    Index Cond: (aggregation_level = 4)
--                                                    Filter: (supervisor_is_test = 0)
--          ->  Hash  (cost=1116.00..1116.00 rows=12900 width=326)
--                ->  Seq Scan on "agg_child_health_2018-05-01_3" agg_child_health  (cost=0.00..1116.00 rows=12900 width=326)
-- (19 rows)



UPDATE "agg_child_health_2018-05-01_2" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2,
        zscore_grading_hfa_normal = ut.zscore_grading_hfa_normal,
				zscore_grading_hfa_moderate = ut.zscore_grading_hfa_moderate,
				zscore_grading_hfa_severe = ut.zscore_grading_hfa_severe,
				zscore_grading_hfa_recorded_in_month = ut.zscore_grading_hfa_recorded_in_month,
				zscore_grading_wfh_recorded_in_month = ut.zscore_grading_wfh_recorded_in_month
    from (
        SELECT
        district_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2,
        SUM(zscore_grading_hfa_normal) as zscore_grading_hfa_normal,
				SUM(zscore_grading_hfa_moderate) as zscore_grading_hfa_moderate,
				SUM(zscore_grading_hfa_severe) as zscore_grading_hfa_severe,
				SUM(zscore_grading_hfa_recorded_in_month) as zscore_grading_hfa_recorded_in_month,
				SUM(zscore_grading_wfh_recorded_in_month) as zscore_grading_wfh_recorded_in_month

        FROM "agg_child_health_2018-05-01_3" agg_child INNER JOIN (SELECT DISTINCT ucr.block_id FROM "awc_location_local" ucr WHERE ucr.block_is_test=0 AND aggregation_level=3) tt ON tt.block_id = agg_child.block_id
        GROUP BY state_id, district_id,gender, age_tranche
    ) ut 
    WHERE agg_child_health.district_id = ut.district_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;


-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2018-05-01_2" agg_child_health  (cost=3868.31..4019.93 rows=1 width=517)
--    ->  Hash Join  (cost=3868.31..4019.93 rows=1 width=517)
--          Hash Cond: ((ut.district_id = agg_child_health.district_id) AND (ut.gender = agg_child_health.gender) AND (ut.age_tranche = agg_child_health.age_tranche))
--          ->  Subquery Scan on ut  (cost=3728.48..3754.28 rows=1290 width=304)
--                ->  HashAggregate  (cost=3728.48..3741.38 rows=1290 width=181)
--                      Group Key: agg_child.state_id, agg_child.district_id, agg_child.gender, agg_child.age_tranche
--                      ->  Hash Join  (cost=1998.06..3147.98 rows=12900 width=125)
--                            Hash Cond: (agg_child.block_id = ucr.block_id)
--                            ->  Seq Scan on "agg_child_health_2018-05-01_3" agg_child  (cost=0.00..1116.00 rows=12900 width=158)
--                            ->  Hash  (cost=1966.26..1966.26 rows=2544 width=32)
--                                  ->  HashAggregate  (cost=1915.38..1940.82 rows=2544 width=32)
--                                        Group Key: ucr.block_id
--                                        ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local ucr  (cost=0.42..1905.49 rows=3954 width=32)
--                                              Index Cond: (aggregation_level = 3)
--                                              Filter: (block_is_test = 0)
--          ->  Hash  (cost=118.94..118.94 rows=1194 width=297)
--                ->  Seq Scan on "agg_child_health_2018-05-01_2" agg_child_health  (cost=0.00..118.94 rows=1194 width=297)
-- (17 rows)

UPDATE "agg_child_health_2018-05-01_1" agg_child_health
    SET wasting_moderate = ut.wasting_moderate,
        wasting_severe = ut.wasting_severe,
        stunting_moderate = ut.stunting_severe,
        stunting_severe = ut.stunting_severe,
        wasting_normal = ut.wasting_normal,
        stunting_normal = ut.stunting_normal,
        wasting_normal_v2 = ut.wasting_normal_v2,
        wasting_moderate_v2 = ut.wasting_moderate_v2,
        wasting_severe_v2 = ut.wasting_severe_v2,
        zscore_grading_hfa_normal = ut.zscore_grading_hfa_normal,
				zscore_grading_hfa_moderate = ut.zscore_grading_hfa_moderate,
				zscore_grading_hfa_severe = ut.zscore_grading_hfa_severe,
				zscore_grading_hfa_recorded_in_month = ut.zscore_grading_hfa_recorded_in_month,
				zscore_grading_wfh_recorded_in_month = ut.zscore_grading_wfh_recorded_in_month
    from (
        SELECT
        state_id,
        gender,
        age_tranche,
        SUM(wasting_moderate) as wasting_moderate,
        SUM(wasting_severe) as wasting_severe,
        SUM(stunting_moderate) as stunting_moderate,
        SUM(stunting_severe) as stunting_severe,
        SUM(wasting_normal) as wasting_normal,
        SUM(stunting_normal) as stunting_normal,
        SUM(wasting_normal_v2) as wasting_normal_v2,
        SUM(wasting_moderate_v2) as wasting_moderate_v2,
        SUM(wasting_severe_v2) as wasting_severe_v2,
        SUM(zscore_grading_hfa_normal) as zscore_grading_hfa_normal,
				SUM(zscore_grading_hfa_moderate) as zscore_grading_hfa_moderate,
				SUM(zscore_grading_hfa_severe) as zscore_grading_hfa_severe,
				SUM(zscore_grading_hfa_recorded_in_month) as zscore_grading_hfa_recorded_in_month,
				SUM(zscore_grading_wfh_recorded_in_month) as zscore_grading_wfh_recorded_in_month

        FROM "agg_child_health_2018-05-01_2" agg_child INNER JOIN (SELECT DISTINCT ucr.district_id FROM "awc_location_local" ucr WHERE ucr.block_is_test=0 AND aggregation_level=2) tt ON tt.district_id = agg_child.district_id
        GROUP BY state_id, tt.district_id,gender, age_tranche
    ) ut 
    WHERE agg_child_health.state_id = ut.state_id and 
      agg_child_health.gender = ut.gender AND
      agg_child_health.age_tranche = ut.age_tranche;

-- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Update on "agg_child_health_2018-05-01_1" agg_child_health  (cost=496.38..510.66 rows=1 width=488)
--    ->  Merge Join  (cost=496.38..510.66 rows=1 width=488)
--          Merge Cond: ((agg_child_health.state_id = ut.state_id) AND (agg_child_health.gender = ut.gender) AND (agg_child_health.age_tranche = ut.age_tranche))
--          ->  Sort  (cost=31.27..31.84 rows=229 width=268)
--                Sort Key: agg_child_health.state_id, agg_child_health.gender, agg_child_health.age_tranche
--                ->  Seq Scan on "agg_child_health_2018-05-01_1" agg_child_health  (cost=0.00..22.29 rows=229 width=268)
--          ->  Sort  (cost=465.12..468.10 rows=1194 width=304)
--                Sort Key: ut.state_id, ut.gender, ut.age_tranche
--                ->  Subquery Scan on ut  (cost=380.21..404.09 rows=1194 width=304)
--                      ->  HashAggregate  (cost=380.21..392.15 rows=1194 width=180)
--                            Group Key: agg_child.state_id, ucr.district_id, agg_child.gender, agg_child.age_tranche
--                            ->  Hash Join  (cost=204.35..326.48 rows=1194 width=124)
--                                  Hash Cond: (agg_child.district_id = ucr.district_id)
--                                  ->  Seq Scan on "agg_child_health_2018-05-01_2" agg_child  (cost=0.00..118.94 rows=1194 width=125)
--                                  ->  Hash  (cost=201.20..201.20 rows=252 width=32)
--                                        ->  HashAggregate  (cost=196.16..198.68 rows=252 width=32)
--                                              Group Key: ucr.district_id
--                                              ->  Index Scan using awc_location_local_aggregation_level_idx on awc_location_local ucr  (cost=0.42..195.18 rows=394 width=32)
--                                                    Index Cond: (aggregation_level = 2)
--                                                    Filter: (block_is_test = 0)
-- (20 rows)



