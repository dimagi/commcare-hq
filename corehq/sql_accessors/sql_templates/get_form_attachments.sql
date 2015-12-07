DROP FUNCTION IF EXISTS get_form_attachments(form_id text);

CREATE FUNCTION get_form_attachments(form_id text) RETURNS SETOF form_processor_xformattachmentsql AS $$
    SELECT * FROM form_processor_xformattachmentsql where form_id = $1;
$$ LANGUAGE SQL;
