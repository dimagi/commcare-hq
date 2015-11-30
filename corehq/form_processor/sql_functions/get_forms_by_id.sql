DROP FUNCTION IF EXISTS get_forms_by_id(form_id text);

CREATE FUNCTION get_forms_by_id(form_ids text[]) RETURNS SETOF form_processor_xforminstancesql AS $$
BEGIN
    SELECT * FROM form_processor_xforminstancesql where form_id = ANY(form_ids);
END;
$$ LANGUAGE plpgsql;
