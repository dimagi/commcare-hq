DROP FUNCTION IF EXISTS get_case_attachment_by_identifier(TEXT, TEXT);

CREATE FUNCTION get_case_attachment_by_identifier(p_case_id TEXT, p_identifier TEXT) RETURNS SETOF form_processor_caseattachmentsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_caseattachmentsql where case_id = p_case_id and identifier = p_identifier;
END;
$$ LANGUAGE plpgsql;
