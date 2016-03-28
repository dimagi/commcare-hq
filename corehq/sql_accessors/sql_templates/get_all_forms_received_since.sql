DROP FUNCTION IF EXISTS get_all_forms_received_since(timestamp with time zone, integer);

CREATE FUNCTION get_all_forms_received_since(reference_date timestamp with time zone, query_limit integer)
RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xforminstancesql as form_table
    WHERE form_table.received_on >= reference_date
    LIMIT query_limit
    ;
END;
$$ LANGUAGE plpgsql;
