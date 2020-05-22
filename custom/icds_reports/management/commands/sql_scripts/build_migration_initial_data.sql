INSERT INTO "icds_dashboard_migration_forms" (
          state_id, supervisor_id, month, person_case_id, is_migrated, migration_date
        ) (
          SELECT DISTINCT
            state_id,
            supervisor_id,
            '2020-03-01'::DATE AS month,
            person_case_id AS person_case_id,
            LAST_VALUE(is_migrated) OVER w AS is_migrated,
            CASE
                WHEN LAST_VALUE(date_left) OVER w IS NULL
                    THEN LAST_VALUE(timeend) OVER w
                ELSE LAST_VALUE(date_left) OVER w
            END AS migration_date
          FROM "ucr_icds-cas_static-migration_form_986e6c8c"
          WHERE timeend<'2020-04-01' AND
                person_case_id IS NOT NULL AND state_id='{state_id}'
          WINDOW w AS (
            PARTITION BY supervisor_id, person_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        )
