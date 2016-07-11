DROP FUNCTION IF EXISTS get_deleted_case_ids_by_owner(TEXT, TEXT);

CREATE FUNCTION get_deleted_case_ids_by_owner(domain_name TEXT, p_owner_id TEXT) RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT case_table.case_id FROM form_processor_commcarecasesql as case_table
    WHERE
      case_table.domain = domain_name
      AND case_table.owner_id = p_owner_id
      AND case_table.deleted = TRUE;
END;
$$ LANGUAGE plpgsql;
