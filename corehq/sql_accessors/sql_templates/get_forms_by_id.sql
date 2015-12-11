DROP FUNCTION IF EXISTS get_forms_by_id(TEXT[]);

CREATE FUNCTION get_forms_by_id(form_ids TEXT[]) RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xforminstancesql where form_id = ANY(form_ids);
END;
$$ LANGUAGE plpgsql;
