DROP FUNCTION IF EXISTS get_modified_case_ids(
    TEXT, TEXT[], TIMESTAMP WITH TIME ZONE, TEXT);

CREATE FUNCTION get_modified_case_ids(
    domain_name TEXT,
    case_ids TEXT[],
    last_sync_date TIMESTAMP WITH TIME ZONE,
    last_sync_id TEXT
) RETURNS TABLE (case_id VARCHAR(255)) AS $$
BEGIN
    RETURN QUERY
    SELECT cases.case_id
    FROM form_processor_commcarecasesql cases
    JOIN (SELECT UNNEST(case_ids) AS case_id) AS cx USING (case_id)
    WHERE domain = domain_name
        AND server_modified_on >= last_sync_date
        AND EXISTS (
            SELECT TRUE
            FROM form_processor_casetransaction trans
            WHERE cases.case_id = trans.case_id
                AND trans.server_date > last_sync_date
                AND trans.sync_log_id IS DISTINCT FROM last_sync_id
        );
END;
$$ LANGUAGE plpgsql;
