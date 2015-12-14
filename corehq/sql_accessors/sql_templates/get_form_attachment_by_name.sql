DROP FUNCTION IF EXISTS get_form_attachment_by_name(TEXT, TEXT);

CREATE FUNCTION get_form_attachment_by_name(p_form_id TEXT, attachment_name TEXT) RETURNS SETOF form_processor_xformattachmentsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xformattachmentsql where form_id = p_form_id and name = attachment_name;
END;
$$ LANGUAGE plpgsql;
