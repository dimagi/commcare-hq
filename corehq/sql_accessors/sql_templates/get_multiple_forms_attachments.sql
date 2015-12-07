DROP FUNCTION IF EXISTS get_mulitple_forms_attachments(text[]);

CREATE FUNCTION get_mulitple_forms_attachments(form_ids text[]) RETURNS SETOF form_processor_xformattachmentsql AS $$
    -- order by form id so that we don't have to do it in python
    SELECT * FROM form_processor_xformattachmentsql where form_id = ANY($1) ORDER BY form_id;
$$ LANGUAGE SQL;
