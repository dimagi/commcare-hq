DROP VIEW IF EXISTS awc_location_months_local CASCADE;
CREATE VIEW awc_location_months_local AS
 SELECT
  awc_location.doc_id as awc_id,
  awc_location.awc_name,
  awc_location.awc_site_code,
  awc_location.supervisor_id,
  awc_location.supervisor_name,
  awc_location.supervisor_site_code,
  awc_location.block_id,
  awc_location.block_name,
  awc_location.block_site_code,
  awc_location.district_id,
  awc_location.district_name,
  awc_location.district_site_code,
  awc_location.state_id,
  awc_location.state_name,
  awc_location.state_site_code,
  awc_location.aggregation_level,
  awc_location.block_map_location_name,
  awc_location.district_map_location_name,
  awc_location.state_map_location_name,
  awc_location.aww_name,
  awc_location.contact_phone_number,
  months.start_date AS month,
  months.month_name AS month_display
  FROM awc_location_local awc_location
  CROSS JOIN "icds_months_local" months;
