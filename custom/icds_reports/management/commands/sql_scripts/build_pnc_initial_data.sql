INSERT INTO "icds_dashboard_ccs_record_postnatal_forms" (
          case_id, month, state_id, supervisor_id, latest_time_end_processed, counsel_methods, is_ebf,
          new_ifa_tablets_total, valid_visits
        ) (

        SELECT
        distinct case_id,
        '2020-03-01'::date as month,
        'f9b47ea2ee2d8a02acddeeb491d3e175' as state_id,
        supervisor_id,
        LAST_VALUE(latest_time_end) OVER w AS latest_time_end_processed,
        MAX(counsel_methods) OVER w AS counsel_methods,
        LAST_VALUE(is_ebf) OVER w as is_ebf,
        LAST_VALUE(new_ifa_tablets_total) OVER w as new_ifa_tablets_total,
        SUM(CASE WHEN (unscheduled_visit=0 AND days_visit_late < 8) OR
            (latest_time_end::DATE - next_visit) < 8 THEN 1 ELSE 0 END) OVER w as valid_visits
        from
        (
            SELECT
            DISTINCT ccs_record_case_id AS case_id,
            LAST_VALUE(timeend) OVER w AS latest_time_end,
            MAX(counsel_methods) OVER w AS counsel_methods,
            LAST_VALUE(is_ebf) OVER w as is_ebf,
            LAST_VALUE(unscheduled_visit) OVER w as unscheduled_visit,
            LAST_VALUE(days_visit_late) OVER w as days_visit_late,
            LAST_VALUE(next_visit) OVER w as next_visit,
            LAST_VALUE(new_ifa_tablets_total) OVER w as new_ifa_tablets_total,
            supervisor_id
            FROM "ucr_icds-cas_static-postnatal_care_forms_0c30d94e"
            WHERE timeend < '2020-04-01' AND state_id = 'f9b47ea2ee2d8a02acddeeb491d3e175'
            WINDOW w AS (
                PARTITION BY doc_id, supervisor_id, ccs_record_case_id
                ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
        ) ut
        WINDOW w AS (
            PARTITION BY supervisor_id, case_id
            ORDER BY latest_time_end RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        )
