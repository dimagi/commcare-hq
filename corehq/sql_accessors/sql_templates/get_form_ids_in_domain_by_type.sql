-- drop it first in case we're changing the signature in which case 'CREATE OR REPLACE' will fail
DROP FUNCTION IF EXISTS get_form_ids_in_domain_by_type(TEXT, INTEGER);

-- return SETOF so that we get 0 rows when no form matches otherwise we'll get an empty row
CREATE FUNCTION get_form_ids_in_domain_by_type(domain_name TEXT, p_state INTEGER DEFAULT 1) RETURNS TABLE (form_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT form_table.form_id FROM form_processor_xforminstancesql as form_table
    WHERE form_table.domain = domain_name
      AND form_table.state = p_state;
END;
$$ LANGUAGE plpgsql;
