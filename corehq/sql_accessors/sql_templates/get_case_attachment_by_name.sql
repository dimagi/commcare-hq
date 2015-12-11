DROP FUNCTION IF EXISTS get_case_attachment_by_name(TEXT, TEXT);

CREATE FUNCTION get_case_attachment_by_name(p_case_id TEXT, case_name TEXT) RETURNS SETOF form_processor_caseattachmentsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_caseattachmentsql where case_id = p_case_id and name = case_name;
END;
$$ LANGUAGE plpgsql;
