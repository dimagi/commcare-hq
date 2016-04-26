DROP FUNCTION IF EXISTS soft_delete_cases(TEXT, TEXT[], TIMESTAMP, TIMESTAMP, TEXT);

CREATE FUNCTION soft_delete_cases(
    p_domain TEXT,
    case_ids TEXT[],
    p_server_modified_on TIMESTAMP,
    deletion_date TIMESTAMP,
    deletion_id TEXT DEFAULT NULL) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
