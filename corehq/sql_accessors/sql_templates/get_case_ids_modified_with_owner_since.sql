DROP FUNCTION IF EXISTS get_case_ids_modified_with_owner_since(text, text, timestamp with time zone);

CREATE FUNCTION get_case_ids_modified_with_owner_since(domain_name text, p_owner_id text, reference_date timestamp with time zone)
RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT case_table.case_id FROM form_processor_commcarecasesql as case_table
    WHERE case_table.domain = domain_name
      AND case_table.server_modified_on >= reference_date
      -- AND owner_id matches OR (owner_id is falsey AND modified_by matches)
      AND (
         case_table.owner_id = p_owner_id
         OR (
           (case_table.owner_id IS NULL OR case_table.owner_id = '') AND case_table.modified_by = p_owner_id
         )
      )
    ;
END;
$$ LANGUAGE plpgsql;
