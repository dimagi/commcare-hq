DROP FUNCTION IF EXISTS filter_open_case_ids(TEXT, TEXT[]);

CREATE FUNCTION filter_open_case_ids(
    domain_name TEXT,
    case_ids_array TEXT[]
) RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT form_processor_commcarecasesql.case_id
    FROM form_processor_commcarecasesql
    JOIN (SELECT UNNEST(case_ids_array) AS case_id) AS cx USING (case_id)
    WHERE domain = domain_name AND NOT closed AND NOT deleted;
END;
$$ LANGUAGE plpgsql;
