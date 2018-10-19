--Aggregate Location TABLE
CREATE OR REPLACE FUNCTION aggregate_location_table() RETURNS VOID AS
$BODY$
DECLARE
  all_text text;
  null_value text;
BEGIN
  all_text = 'All';
  null_value = NULL;

  EXECUTE 'INSERT INTO awc_location (
     doc_id,
     awc_name,
     awc_site_code,
     supervisor_id,
     supervisor_name,
     supervisor_site_code,
     block_id,
     block_name,
     block_site_code,
     district_id,
     district_name,
     district_site_code,
     state_id,
     state_name,
     state_site_code,
     aggregation_level,
     block_map_location_name,
     district_map_location_name,
     state_map_location_name,
     aww_name,
     contact_phone_number,
     state_is_test,
     district_is_test,
     block_is_test,
     supervisor_is_test,
     awc_is_test
    )
    (SELECT ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    'supervisor_id, ' ||
    'supervisor_name, ' ||
    'supervisor_site_code, ' ||
    'block_id, ' ||
    'block_name, ' ||
    'block_site_code, ' ||
    'district_id, ' ||
    'district_name, ' ||
    'district_site_code, ' ||
    'state_id, ' ||
    'state_name, ' ||
    'state_site_code, ' ||
    '4, ' ||
    'block_map_location_name, ' ||
    'district_map_location_name, ' ||
    'state_map_location_name,' ||
    'NULL, ' ||
    'NULL, ' ||
    'state_is_test, ' ||
    'district_is_test, ' ||
    'block_is_test, ' ||
    'supervisor_is_test, ' ||
    '0 ' ||
    'FROM awc_location GROUP BY ' ||
    'supervisor_id, supervisor_name, supervisor_site_code, ' ||
    'block_id, block_name, block_site_code,' ||
    'district_id, district_name, district_site_code,' ||
    'state_id, state_name, state_site_code, ' ||
    'block_map_location_name, district_map_location_name, state_map_location_name, ' ||
    'state_is_test, district_is_test, block_is_test, supervisor_is_test' ||
    ')';

  EXECUTE 'INSERT INTO awc_location 
    (
     doc_id,
     awc_name,
     awc_site_code,
     supervisor_id,
     supervisor_name,
     supervisor_site_code,
     block_id,
     block_name,
     block_site_code,
     district_id,
     district_name,
     district_site_code,
     state_id,
     state_name,
     state_site_code,
     aggregation_level,
     block_map_location_name,
     district_map_location_name,
     state_map_location_name,
     aww_name,
     contact_phone_number,
     state_is_test,
     district_is_test,
     block_is_test,
     supervisor_is_test,
     awc_is_test
    )
    (SELECT ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    'block_id, ' ||
    'block_name, ' ||
    'block_site_code, ' ||
    'district_id, ' ||
    'district_name, ' ||
    'district_site_code, ' ||
    'state_id, ' ||
    'state_name, ' ||
    'state_site_code, ' ||
    '3, ' ||
    'block_map_location_name, ' ||
    'district_map_location_name, ' ||
    'state_map_location_name, ' ||
    'NULL, ' ||
    'NULL, ' ||
    'state_is_test, ' ||
    'district_is_test, ' ||
    'block_is_test, ' ||
    '0, ' ||
    '0 ' ||
    'FROM awc_location GROUP BY ' ||
    'block_id, block_name, block_site_code,' ||
    'district_id, district_name, district_site_code,' ||
    'state_id, state_name, state_site_code, ' ||
    'block_map_location_name, district_map_location_name, state_map_location_name, ' ||
    'state_is_test, district_is_test, block_is_test' ||
    ')';

  EXECUTE 'INSERT INTO awc_location 
    (
     doc_id,
     awc_name,
     awc_site_code,
     supervisor_id,
     supervisor_name,
     supervisor_site_code,
     block_id,
     block_name,
     block_site_code,
     district_id,
     district_name,
     district_site_code,
     state_id,
     state_name,
     state_site_code,
     aggregation_level,
     block_map_location_name,
     district_map_location_name,
     state_map_location_name,
     aww_name,
     contact_phone_number,
     state_is_test,
     district_is_test,
     block_is_test,
     supervisor_is_test,
     awc_is_test
    )
    (SELECT ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    'district_id, ' ||
    'district_name, ' ||
    'district_site_code, ' ||
    'state_id, ' ||
    'state_name, ' ||
    'state_site_code, ' ||
    '2, ' ||
    quote_nullable(null_value) || ', ' ||
    'district_map_location_name, ' ||
    'state_map_location_name,' ||
    'NULL, ' ||
    'NULL, ' ||
    'state_is_test, ' ||
    'district_is_test, ' ||
    '0, ' ||
    '0, ' ||
    '0 ' ||
    'FROM awc_location GROUP BY ' ||
    'district_id, district_name, district_site_code,' ||
    'state_id, state_name, state_site_code, ' ||
    'district_map_location_name, state_map_location_name, ' ||
    'state_is_test, district_is_test' ||
    ')';

  EXECUTE 'INSERT INTO awc_location 
    (
     doc_id,
     awc_name,
     awc_site_code,
     supervisor_id,
     supervisor_name,
     supervisor_site_code,
     block_id,
     block_name,
     block_site_code,
     district_id,
     district_name,
     district_site_code,
     state_id,
     state_name,
     state_site_code,
     aggregation_level,
     block_map_location_name,
     district_map_location_name,
     state_map_location_name,
     aww_name,
     contact_phone_number,
     state_is_test,
     district_is_test,
     block_is_test,
     supervisor_is_test,
     awc_is_test
    )
    (SELECT ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(all_text) || ', ' ||
    'state_id, ' ||
    'state_name, ' ||
    'state_site_code, ' ||
    '1, ' ||
    quote_nullable(null_value) || ', ' ||
    quote_nullable(null_value) || ', ' ||
    'state_map_location_name,' ||
    'NULL, ' ||
    'NULL, ' ||
    'state_is_test, ' ||
    '0, ' ||
    '0, ' ||
    '0, ' ||
    '0 ' ||
    'FROM awc_location GROUP BY ' ||
    'state_id, state_name, state_site_code, state_map_location_name, ' ||
    'state_is_test' ||
    ')';
END;
$BODY$
LANGUAGE plpgsql;
