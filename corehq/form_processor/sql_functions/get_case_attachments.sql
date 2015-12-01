DROP FUNCTION IF EXISTS get_case_attachments(text);

CREATE FUNCTION get_case_attachments(case_id text) RETURNS SETOF form_processor_caseattachmentsql AS $$
    SELECT * FROM form_processor_caseattachmentsql where case_id = $1;
$$ LANGUAGE SQL;
