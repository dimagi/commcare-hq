DROP FUNCTION IF EXISTS get_mulitple_forms_attachments(TEXT[]);

CREATE FUNCTION get_mulitple_forms_attachments(form_ids TEXT[]) RETURNS SETOF form_processor_xformattachmentsql AS $$
BEGIN
    -- order by form id so that we don't have to do it in python
    RETURN QUERY
    SELECT * FROM form_processor_xformattachmentsql where form_id = ANY(form_ids) ORDER BY form_id;
END;
$$ LANGUAGE plpgsql;
