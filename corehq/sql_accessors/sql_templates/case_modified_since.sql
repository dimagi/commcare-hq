DROP FUNCTION IF EXISTS case_modified_since(TEXT, TIMESTAMP);

CREATE FUNCTION case_modified_since(p_case_id TEXT, p_server_modified_on TIMESTAMP, case_modified OUT BOOLEAN) AS $$
BEGIN
    SELECT NOT exists(
        SELECT 1 FROM form_processor_commcarecasesql
        WHERE form_processor_commcarecasesql.case_id = p_case_id
          AND form_processor_commcarecasesql.server_modified_on = p_server_modified_on AT TIME ZONE 'UTC'
    ) INTO case_modified;
END;
$$ LANGUAGE plpgsql;
