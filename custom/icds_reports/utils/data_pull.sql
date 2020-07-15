CREATE TABLE tmp_daily_attendance_rank AS
    SELECT
        awc_id,
        pse_date,
        form_location_lat,
        form_location_long,
        rank() OVER (
            PARTITION BY supervisor_id,awc_id
            ORDER BY pse_date DESC
            )
    FROM daily_attendance WHERE state_id='039bbe4a40de499ea87b9761537dd611' AND image_name IS NOT NULL
    
--                                                                               QUERY PLAN
-- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
--  Custom Scan (Citus Real-Time)  (cost=0.00..0.00 rows=0 width=0)
--    Task Count: 64
--    Tasks Shown: One of 64
--    ->  Task
--          Node: host=100.71.184.232 port=6432 dbname=icds_ucr
--          ->  WindowAgg  (cost=47078.26..47078.57 rows=14 width=100)
--                ->  Sort  (cost=47078.26..47078.29 rows=14 width=92)
--                      Sort Key: daily_attendance.supervisor_id, daily_attendance.awc_id, daily_attendance.pse_date DESC
--                      ->  Index Scan using ix_daily_attendance_month_state_id_102776 on daily_attendance_102776 daily_attendance  (cost=0.56..47077.99 rows=14 width=92)
--                            Index Cond: (state_id = '039bbe4a40de499ea87b9761537dd611'::text)
--                            Filter: (image_name IS NOT NULL)
-- (11 rows)

SELECT
        "awc_location_local"."doc_id" AS "awc_id",
        "awc_location_local"."awc_name" AS "awc_name",
        "awc_location_local"."awc_site_code" AS "awc_site_code",
        "awc_location_local"."supervisor_name" AS "supervisor_name",
        "awc_location_local"."block_name" AS "block_name",
        "awc_location_local"."district_name" AS "district_name",
        ut.pse_date_1,
        ut.form_location_lat_1,
        ut.form_location_long_1,
        ut.pse_date_2,
        ut.form_location_lat_2,
        ut.form_location_long_2,
        ut.pse_date_3,
        ut.form_location_lat_3,
        ut.form_location_long_3
    FROM "awc_location_local"
    LEFT JOIN "public"."agg_awc" "agg_awc" ON (
        ("awc_location_local"."aggregation_level" = "agg_awc"."aggregation_level") AND
        ("awc_location_local"."state_id" = "agg_awc"."state_id") AND
        ("awc_location_local"."district_id" = "agg_awc"."district_id") AND
        ("awc_location_local"."block_id" = "agg_awc"."block_id") AND
        ("awc_location_local"."supervisor_id" = "agg_awc"."supervisor_id") AND
        ("awc_location_local"."doc_id" = "agg_awc"."awc_id")
    )
    LEFT JOIN (
        SELECT
            awc_id,
            MIN(CASE WHEN rank=1 THEN pse_date END) as pse_date_1,
            MIN(CASE WHEN rank=1 THEN form_location_lat  END) as form_location_lat_1,
            MIN(CASE WHEN rank=1 THEN form_location_long  END) as form_location_long_1,
            MIN(CASE WHEN rank=2 THEN pse_date END) as pse_date_2,
            MIN(CASE WHEN rank=2 THEN form_location_lat  END) as form_location_lat_2,
            MIN(CASE WHEN rank=2 THEN form_location_long  END) as form_location_long_2,
            MIN(CASE WHEN rank=3 THEN pse_date END) as pse_date_3,
            MIN(CASE WHEN rank=3 THEN form_location_lat  END) as form_location_lat_3,
            MIN(CASE WHEN rank=3 THEN form_location_long  END) as form_location_long_3
        FROM tmp_daily_attendance_rank
        group by awc_id
    ) ut ON ( ut.awc_id = "awc_location_local".doc_id)
    WHERE "agg_awc"."num_launched_awcs" >0 AND "awc_location_local"."aggregation_level" =5 AND "agg_awc"."month"='2020-07-01' AND "awc_location_local"."state_id" = '039bbe4a40de499ea87b9761537dd611'
    
DROP TABLE IF EXISTS tmp_daily_attendance_rank;



