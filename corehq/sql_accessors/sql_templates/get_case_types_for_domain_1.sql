DROP FUNCTION IF EXISTS get_case_types_for_domain(TEXT);

CREATE FUNCTION get_case_types_for_domain(p_domain TEXT) RETURNS TABLE (case_type VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT form_processor_commcarecasesql.type
    FROM form_processor_commcarecasesql
    WHERE form_processor_commcarecasesql.domain = p_domain
        AND form_processor_commcarecasesql.deleted = FALSE;
END;
$$ LANGUAGE plpgsql;
