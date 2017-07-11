DROP FUNCTION IF EXISTS get_modified_case_ids(
    TEXT, TEXT[], TIMESTAMP WITH TIME ZONE, TEXT);

CREATE FUNCTION get_modified_case_ids(
    domain_name TEXT,
    case_ids TEXT[],
    last_sync_date TIMESTAMP WITH TIME ZONE,
    last_sync_id TEXT
) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
