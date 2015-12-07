DROP FUNCTION IF EXISTS get_form_attachment_by_name(form_id text, name text);

CREATE FUNCTION get_form_attachment_by_name(form_id text, name text) RETURNS SETOF form_processor_xformattachmentsql AS $$
    SELECT * FROM form_processor_xformattachmentsql where form_id = $1 and name = $2;
$$ LANGUAGE SQL;
