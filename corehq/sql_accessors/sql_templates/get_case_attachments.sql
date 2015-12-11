DROP FUNCTION IF EXISTS get_case_attachments(TEXT);

CREATE FUNCTION get_case_attachments(p_case_id TEXT) RETURNS SETOF form_processor_caseattachmentsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_caseattachmentsql where case_id = p_case_id;
END;
$$ LANGUAGE plpgsql;
