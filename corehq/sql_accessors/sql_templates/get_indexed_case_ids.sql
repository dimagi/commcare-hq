DROP FUNCTION IF EXISTS get_indexed_case_ids(text, text[]);

CREATE FUNCTION get_indexed_case_ids(domain_name text, case_ids text[]) RETURNS TABLE (referenced_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT case_index_table.referenced_id FROM form_processor_commcarecaseindexsql AS case_index_table
    WHERE
      -- case_index_table.domain = domain_name AND -- TODO: Uncomment if domain is ever saved in CaseIndex column
      case_index_table.case_id = ANY(case_ids)
    ;
END;
$$ LANGUAGE plpgsql;
