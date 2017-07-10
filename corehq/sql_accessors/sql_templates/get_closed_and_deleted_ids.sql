DROP FUNCTION IF EXISTS get_closed_and_deleted_ids(TEXT, TEXT[]);

CREATE FUNCTION get_closed_and_deleted_ids(
    domain_name TEXT,
    case_ids_array TEXT[]
) RETURNS TABLE (case_id VARCHAR(255), closed BOOLEAN, deleted BOOLEAN) AS $$
BEGIN
    RETURN QUERY
    SELECT cases.case_id, cases.closed, cases.deleted
    FROM form_processor_commcarecasesql cases
    JOIN (SELECT UNNEST(case_ids_array) AS case_id) AS cx USING (case_id)
    WHERE domain = domain_name AND (cases.closed or cases.deleted);
END;
$$ LANGUAGE plpgsql;
