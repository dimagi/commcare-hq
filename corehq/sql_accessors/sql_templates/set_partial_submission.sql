DROP FUNCTION IF EXISTS set_partial_submission(TEXT);

CREATE FUNCTION set_partial_submission(p_form_id TEXT) RETURNS VOID AS $$
BEGIN
    UPDATE form_processor_xforminstancesql SET partial_submission = TRUE WHERE form_processor_xforminstancesql.form_id = p_form_id;
END;
$$ LANGUAGE plpgsql;
