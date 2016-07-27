DROP FUNCTION IF EXISTS get_all_forms_received_since(timestamp with time zone, INTEGER, INTEGER);

CREATE FUNCTION get_all_forms_received_since(reference_date timestamp with time zone, last_id INTEGER, query_limit integer)
RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    RETURN QUERY
    SELECT forms.* FROM (
        SELECT * FROM form_processor_xforminstancesql as form_table
        WHERE form_table.received_on >= reference_date
        LIMIT query_limit + 1
    ) AS forms
    WHERE forms.id > last_id
    ORDER BY forms.received_on, forms.id
    LIMIT query_limit
    ;
END;
$$ LANGUAGE plpgsql;
