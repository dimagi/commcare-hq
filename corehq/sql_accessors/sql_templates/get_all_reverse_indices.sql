DROP FUNCTION IF EXISTS get_all_reverse_indices(TEXT, TEXT[]);

CREATE FUNCTION get_all_reverse_indices(domain_name, TEXT, case_ids TEXT[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecaseindexsql AS case_index_table
    WHERE
      case_index_table.domain = domain_name AND
      case_index_table.referenced_id = ANY(case_ids)
    ;
END;
$$ LANGUAGE plpgsql;
