DROP FUNCTION IF EXISTS get_mulitple_forms_attachments(form_id text);

CREATE FUNCTION get_mulitple_forms_attachments(form_ids text[]) RETURNS SETOF form_processor_xformattachmentsql AS $$
    -- order by form id so that we don't have to do it in python
    SELECT * FROM form_processor_xformattachmentsql where form_id = ANY(form_ids) ORDER BY form_id;
$$ LANGUAGE SQL;
