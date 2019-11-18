DROP VIEW IF EXISTS daily_attendance_view CASCADE;
CREATE VIEW daily_attendance_view AS
    SELECT "awc_location_months"."awc_id" AS "awc_id",
        "awc_location_months"."awc_name" AS "awc_name",
        "awc_location_months"."awc_site_code" AS "awc_site_code",
        "awc_location_months"."supervisor_id" AS "supervisor_id",
        "awc_location_months"."supervisor_name" AS "supervisor_name",
        "awc_location_months"."supervisor_site_code" AS "supervisor_site_code",
        "awc_location_months"."block_id" AS "block_id",
        "awc_location_months"."block_name" AS "block_name",
        "awc_location_months"."block_site_code" AS "block_site_code",
        "awc_location_months"."district_id" AS "district_id",
        "awc_location_months"."district_name" AS "district_name",
        "awc_location_months"."district_site_code" AS "district_site_code",
        "awc_location_months"."state_id" AS "state_id",
        "awc_location_months"."state_name" AS "state_name",
        "awc_location_months"."state_site_code" AS "state_site_code",
        "awc_location_months"."aggregation_level" AS "aggregation_level",
        "awc_location_months"."block_map_location_name" AS "block_map_location_name",
        "awc_location_months"."district_map_location_name" AS "district_map_location_name",
        "awc_location_months"."state_map_location_name" AS "state_map_location_name",
        "awc_location_months"."month" AS "month",
        "awc_location_months"."contact_phone_number" AS "contact_phone_number",
        "daily_attendance"."doc_id" AS "doc_id",
        "daily_attendance"."pse_date" AS "pse_date",
        "daily_attendance"."awc_open_count" AS "awc_open_count",
        "daily_attendance"."count" AS "count",
        "daily_attendance"."eligible_children" AS "eligible_children",
        "daily_attendance"."attended_children" AS "attended_children",
        "daily_attendance"."attended_children_percent" AS "attended_children_percent",
        "daily_attendance"."form_location" AS "form_location",
        "daily_attendance"."form_location_lat" AS "form_location_lat",
        "daily_attendance"."form_location_long" AS "form_location_long",
        "daily_attendance"."image_name" AS "image_name"
    FROM "public"."awc_location_months" "awc_location_months"
    JOIN "public"."daily_attendance" "daily_attendance" ON (
        ("awc_location_months"."awc_id" = "daily_attendance"."awc_id") AND
        ("awc_location_months"."month" = "daily_attendance"."month")
    );
