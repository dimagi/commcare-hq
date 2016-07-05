DROP FUNCTION IF EXISTS get_all_reverse_indices(TEXT, TEXT[]);

CREATE FUNCTION get_all_reverse_indices(domain_name TEXT, case_ids TEXT[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    SELECT case_index_table.* FROM form_processor_commcarecaseindexsql AS case_index_table
    INNER JOIN form_processor_commcarecasesql AS case_table on case_index_table.case_id = case_table.case_id
    WHERE
      case_table.deleted = False AND
      case_index_table.domain = domain_name AND
      case_index_table.referenced_id = ANY(case_ids)
    ;
END;
$$ LANGUAGE plpgsql;
