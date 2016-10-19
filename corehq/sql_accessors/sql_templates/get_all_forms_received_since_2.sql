DROP FUNCTION IF EXISTS get_all_forms_received_since(timestamp with time zone, INTEGER, INTEGER);

CREATE FUNCTION get_all_forms_received_since(reference_date timestamp with time zone, last_id INTEGER, query_limit integer)
RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xforminstancesql as form_table
        WHERE (form_table.received_on, form_table.id) > (reference_date, last_id)
        ORDER BY form_table.received_on, form_table.id
        LIMIT query_limit;
END;
$$ LANGUAGE plpgsql;
