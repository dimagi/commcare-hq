DROP FUNCTION IF EXISTS get_case_last_modified_dates(text, text[]);

CREATE FUNCTION get_case_last_modified_dates(domain_name text, case_ids text[])
  RETURNS TABLE (case_id VARCHAR(255), server_modified_on timestamp with time zone) AS $$
BEGIN
    RETURN QUERY
    SELECT case_table.case_id, case_table.server_modified_on FROM form_processor_commcarecasesql AS case_table
    WHERE
      case_table.domain = domain_name
      AND case_table.case_id = ANY(case_ids)
    ;
END;
$$ LANGUAGE plpgsql;
