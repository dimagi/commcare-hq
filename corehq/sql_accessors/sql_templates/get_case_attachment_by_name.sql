DROP FUNCTION IF EXISTS get_case_attachment_by_name(text, text);

CREATE FUNCTION get_case_attachment_by_name(case_id text, name text) RETURNS SETOF form_processor_caseattachmentsql AS $$
    SELECT * FROM form_processor_caseattachmentsql where case_id = $1 and name = $2;
$$ LANGUAGE SQL;
