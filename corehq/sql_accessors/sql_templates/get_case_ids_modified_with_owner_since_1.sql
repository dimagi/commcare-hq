DROP FUNCTION IF EXISTS get_case_ids_modified_with_owner_since(TEXT, TEXT, TIMESTAMP WITH TIME ZONE);

CREATE FUNCTION get_case_ids_modified_with_owner_since(domain_name TEXT, p_owner_id TEXT, reference_date TIMESTAMP WITH TIME ZONE)
RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT case_table.case_id FROM form_processor_commcarecasesql as case_table
    WHERE case_table.domain = domain_name
      AND case_table.server_modified_on >= reference_date
      AND case_table.owner_id = p_owner_id
      AND case_table.deleted = FALSE
    ;
END;
$$ LANGUAGE plpgsql;
