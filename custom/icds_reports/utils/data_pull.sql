CREATE TABLE tmp_daily_attendance AS
    SELECT
        awc_id,
        pse_date,
        form_location_lat,
        form_location_long
        FROM daily_attendance_view WHERE state_id='7fb6f3fe5e7540e7be63c848c28c97ed' AND image_name IS NOT NULL ORDER BY pse_date DESC

CREATE TABLE tmp_daily_attendance_rank AS
    SELECT
        awc_id,
        pse_date,
        form_location_lat,
        form_location_long,
        rank() OVER (
            PARTITION BY awc_id
            ORDER BY pse_date DESC
            )

    FROM tmp_daily_attendance

CREATE TABLE tmp_awc_location_launched AS
    SELECT
        district_name,
        block_name,
        supervisor_name,
        awc_site_code,
        awc_name,
        awc_id
        FROM agg_awc_monthly WHERE num_launched_awcs >0 AND aggregation_level=5 AND month='2020-06-01'

SELECT
    t.district_name,
    t.block_name,
    t.supervisor_name,
    t.awc_site_code,
    t.awc_name,
    t.awc_id,
    ut.pse_date_1,
    ut.form_location_lat_1,
    ut.form_location_long_1,
    ut.pse_date_2,
    ut.form_location_lat_2,
    ut.form_location_long_2,
    ut.pse_date_3,
    ut.form_location_lat_3,
    ut.form_location_long_3
    FROM tmp_awc_location_launched t
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
    ) ut ON ( ut.awc_id = t.awc_id)
    
DROP TABLE IF EXISTS tmp_daily_attendance;
DROP TABLE IF EXISTS tmp_daily_attendance_rank;
DROP TABLE IF EXISTS tmp_awc_location_launched;



