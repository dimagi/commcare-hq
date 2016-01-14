DROP FUNCTION IF EXISTS get_case_ids_in_domain_by_owners(text, text[]);

CREATE FUNCTION get_case_ids_in_domain_by_owners(domain_name text, owner_ids text[]) RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT form_processor_commcarecasesql.case_id FROM form_processor_commcarecasesql
    WHERE form_processor_commcarecasesql.owner_id = ANY(owner_ids)
      AND form_processor_commcarecasesql.domain = domain_name;
END;
$$ LANGUAGE plpgsql;
