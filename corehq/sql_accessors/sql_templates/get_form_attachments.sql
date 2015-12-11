DROP FUNCTION IF EXISTS get_form_attachments(TEXT);

CREATE FUNCTION get_form_attachments(p_form_id TEXT) RETURNS SETOF form_processor_xformattachmentsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_xformattachmentsql where form_id = p_form_id;
END;
$$ LANGUAGE plpgsql;
