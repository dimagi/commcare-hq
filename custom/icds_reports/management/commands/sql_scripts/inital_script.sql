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
                '2017-03-01'::DATE AS month,
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
            WHERE  timeend < '2017-04-01' AND child_health_case_id IS NOT NULL AND state_id IS NOT NULL AND state_id <> ''
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
                ));

-- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Router)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  Insert on icds_dashboard_growth_monitoring_forms_102264 citus_table_alias  (cost=209507.69..209514.65 rows=87 width=371)
--                ->  Subquery Scan on "*SELECT*"  (cost=209507.69..209514.65 rows=87 width=371)
--                      ->  Unique  (cost=209507.69..209511.38 rows=87 width=267)
--                            ->  Sort  (cost=209507.69..209507.90 rows=87 width=267)
--                                  Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".state_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (GREATEST(CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END, CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::timestamp without time zone ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?) END, '1970-01-01 00:00:00'::timestamp without time zone)), (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child) OVER (?)) IS NULL) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::smallint ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) END), (CASE WHEN ((last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh) OVER (?)) = 0) THEN NULL::timestamp without time zone ELSE (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?)) END), (CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::smallint ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) END), (CASE WHEN (last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading) OVER (?) = 0) THEN NULL::timestamp without time zone ELSE last_value("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend) OVER (?) END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id
--                                  ->  WindowAgg  (cost=209498.79..209504.88 rows=87 width=267)
--                                        ->  Sort  (cost=209498.79..209499.01 rows=87 width=264)
--                                              Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".muac_grading = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                              ->  WindowAgg  (cost=209492.73..209495.99 rows=87 width=264)
--                                                    ->  Sort  (cost=209492.73..209492.95 rows=87 width=254)
--                                                          Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfh = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                          ->  WindowAgg  (cost=209486.66..209489.93 rows=87 width=254)
--                                                                ->  Sort  (cost=209486.66..209486.88 rows=87 width=244)
--                                                                      Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_hfa = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                      ->  WindowAgg  (cost=209480.60..209483.86 rows=87 width=244)
--                                                                            ->  Sort  (cost=209480.60..209480.81 rows=87 width=234)
--                                                                                  Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".zscore_grading_wfa = 0) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                                  ->  WindowAgg  (cost=209474.53..209477.79 rows=87 width=234)
--                                                                                        ->  Sort  (cost=209474.53..209474.75 rows=87 width=194)
--                                                                                              Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".height_child IS NULL) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                                              ->  WindowAgg  (cost=209468.47..209471.73 rows=87 width=194)
--                                                                                                    ->  Sort  (cost=209468.47..209468.68 rows=87 width=154)
--                                                                                                          Sort Key: "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".supervisor_id, "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".child_health_case_id, (CASE WHEN ("ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".weight_child IS NULL) THEN 0 ELSE 1 END), "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625".timeend
--                                                                                                          ->  Index Scan using "ix_ucr_icds-cas_static-dashboard_growth_moni_4ebf0_cad42_103610" on "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625_103610" "ucr_icds-cas_static-dashboard_growth_moni_4ebf0625"  (cost=0.56..209465.66 rows=87 width=154)
--                                                                                                                Index Cond: ((state_id IS NOT NULL) AND (timeend < '2017-04-01 00:00:00'::timestamp without time zone))
--                                                                                                                Filter: ((child_health_case_id IS NOT NULL) AND (state_id <> ''::text) AND (worker_hash(supervisor_id) >= '-2147483648'::integer) AND (worker_hash(supervisor_id) <= '-2080374785'::integer))
