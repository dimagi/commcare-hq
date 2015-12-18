DROP FUNCTION IF EXISTS get_case_ids_modified_with_owner_since(text, text, timestamp with time zone);

CREATE FUNCTION get_case_ids_modified_with_owner_since(domain_name text, p_owner_id text, reference_date timestamp with time zone)
RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT case_table.case_id FROM form_processor_commcarecasesql as case_table
    WHERE case_table.domain = domain_name
      AND case_table.server_modified_on >= reference_date
      AND p_owner_id = COALESCE(NULLIF(case_table.owner_id, ''), NULLIF(case_table.modified_by, ''))
    ;
END;
$$ LANGUAGE plpgsql;
