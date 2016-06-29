DROP FUNCTION IF EXISTS get_extension_case_ids(text, text[]);

CREATE FUNCTION get_extension_case_ids(domain_name text, case_ids text[]) RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT case_index_table.case_id
        FROM form_processor_commcarecaseindexsql AS case_index_table
            INNER JOIN form_processor_commcarecasesql AS case_table on case_index_table.case_id = case_table.case_id
    WHERE
      case_table.deleted = FALSE AND
      case_index_table.domain = domain_name AND
      case_index_table.referenced_id = ANY(case_ids)
      AND case_index_table.relationship_id = {{ RELATIONSHIP_TYPE_EXTENSION }}
    ;
END;
$$ LANGUAGE plpgsql;
