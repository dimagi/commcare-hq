-- Copy into daily_attendance
CREATE OR REPLACE FUNCTION insert_into_daily_attendance(date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename text;
  _daily_attendance_tablename text;
  _start_date date;
BEGIN
  _start_date = date_trunc('MONTH', $1)::DATE;
  _tablename := 'daily_attendance' || '_' || _start_date;
  EXECUTE 'SELECT table_name FROM ucr_table_name_mapping WHERE table_type = ' || quote_literal('daily_feeding') INTO _daily_attendance_tablename;

  EXECUTE 'DELETE FROM ' || quote_ident(_tablename);
  EXECUTE 'INSERT INTO ' || quote_ident(_tablename) || ' ' ||
    '(SELECT DISTINCT ON (awc_id, submitted_on) ' ||
    'doc_id, ' ||
    'awc_id, ' ||
    'month, ' ||
    'submitted_on AS pse_date, ' ||
    'awc_open_count, ' ||
    '1, ' ||
    'eligible_children, ' ||
    'attended_children, ' ||
    'attended_children_percent, ' ||
    'form_location, ' ||
    'form_location_lat, ' ||
    'form_location_long, ' ||
    'image_name, ' ||
    'pse_conducted ' ||
    'FROM ' || quote_ident(_daily_attendance_tablename) || ' ' ||
    'WHERE month = ' || quote_literal(_start_date) || ' ' ||
    'ORDER BY awc_id, submitted_on, inserted_at DESC)';

  EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx1') || ' ON ' || quote_ident(_tablename) || '(awc_id)';
        -- There may be better indexes to put here. Should investigate what tableau queries
END;
$BODY$
LANGUAGE plpgsql;
