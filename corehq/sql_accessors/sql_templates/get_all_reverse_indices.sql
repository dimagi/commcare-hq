DROP FUNCTION IF EXISTS get_all_reverse_indices(text[]);

CREATE FUNCTION get_all_reverse_indices(case_ids text[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecaseindexsql AS case_index_table
    WHERE
      -- case_index_table.domain = domain_name AND -- TODO: Uncomment if CaseIndex ever uses its domain column
      case_index_table.referenced_id = ANY(case_ids)
    ;
END;
$$ LANGUAGE plpgsql;
