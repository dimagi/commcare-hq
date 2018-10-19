-- Update Locations Table
CREATE OR REPLACE FUNCTION update_location_table() RETURNS VOID AS
$BODY$
DECLARE
  _ucr_location_table text;
  _ucr_aww_tablename text;
BEGIN
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('awc_location') INTO _ucr_location_table;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('aww_user') INTO _ucr_aww_tablename;

  EXECUTE 'DELETE FROM awc_location';
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
    'doc_id, ' ||
    'awc_name, ' ||
    'awc_site_code, ' ||
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
    '5, ' ||
    'block_map_location_name, ' ||
    'district_map_location_name, ' ||
    'state_map_location_name, NULL, NULL, NULL, NULL, NULL, NULL, NULL FROM ' || quote_ident(_ucr_location_table) || ')';

  EXECUTE 'UPDATE awc_location SET ' ||
    'aww_name = ut.aww_name, contact_phone_number = ut.contact_phone_number ' ||
  'FROM (SELECT commcare_location_id, aww_name, contact_phone_number FROM ' || quote_ident(_ucr_aww_tablename) || ') ut ' ||
  'WHERE ut.commcare_location_id = awc_location.doc_id';

  EXECUTE 'UPDATE awc_location SET ' ||
    'state_is_test = ucr_loc.state_is_test, ' ||
    'district_is_test = ucr_loc.district_is_test, ' ||
    'block_is_test = ucr_loc.block_is_test, ' ||
    'supervisor_is_test = ucr_loc.supervisor_is_test, ' ||
    'awc_is_test = ucr_loc.awc_is_test ' ||
  'FROM (SELECT doc_id, state_is_test, district_is_test, block_is_test, supervisor_is_test, awc_is_test FROM ' || quote_ident(_ucr_location_table) || ') ucr_loc ' ||
  'WHERE ucr_loc.doc_id = awc_location.doc_id';

END;
$BODY$
LANGUAGE plpgsql;
