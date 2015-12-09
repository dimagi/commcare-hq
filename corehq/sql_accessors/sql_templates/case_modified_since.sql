DROP FUNCTION IF EXISTS case_modified_since(text, timestamp);

CREATE FUNCTION case_modified_since(case_id text, server_modified_on timestamp, case_modified OUT BOOLEAN) AS $$
BEGIN
    SELECT NOT exists(
        SELECT 1 FROM form_processor_commcarecasesql
        WHERE form_processor_commcarecasesql.case_id = $1
          AND form_processor_commcarecasesql.server_modified_on=$2
    ) INTO case_modified;
END;
$$ LANGUAGE plpgsql;
