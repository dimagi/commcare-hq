-- drop it first in case we're changing the signature in which case 'CREATE OR REPLACE' will fail
DROP FUNCTION IF EXISTS get_form_ids_by_type_and_date(timestamp without time zone, timestamp without time zone, INTEGER);

-- return SETOF so that we get 0 rows when no form matches otherwise we'll get an empty row
CREATE FUNCTION get_form_ids_by_type_and_date(start_date timestamp without time zone, end_date timestamp without time zone, p_state INTEGER DEFAULT 1) RETURNS TABLE (form_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT form_table.form_id FROM form_processor_xforminstancesql as form_table
    WHERE form_table.state = p_state
        AND form_table.received_on >= start_date
        AND form_table.received_on < end_date;
END;
$$ LANGUAGE plpgsql;
