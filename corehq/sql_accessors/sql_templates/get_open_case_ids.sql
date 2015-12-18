DROP FUNCTION IF EXISTS get_open_case_ids(text, text);

CREATE FUNCTION get_open_case_ids(domain_name text, p_owner_id text) RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT case_table.case_id FROM form_processor_commcarecasesql as case_table
    WHERE
      case_table.closed = FALSE
      AND case_table.domain = domain_name
      AND (
        -- owner_id matches
        case_table.owner_id = p_owner_id
        OR (
          -- owner_id is falsey and modified_by matches
          (case_table.owner_id is NULL OR case_table.owner_id = '') AND case_table.modified_by = p_owner_id
        )
      );
END;
$$ LANGUAGE plpgsql;
