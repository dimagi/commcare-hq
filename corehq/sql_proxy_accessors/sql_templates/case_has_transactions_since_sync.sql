DROP FUNCTION IF EXISTS case_has_transactions_since_sync(TEXT, TEXT, TIMESTAMP WITH TIME ZONE);

CREATE FUNCTION case_has_transactions_since_sync(p_case_id TEXT, p_sync_log_id TEXT, sync_log_date TIMESTAMP WITH TIME ZONE )
RETURNS BOOLEAN AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_case_id, 'siphash24');
$$ LANGUAGE plproxy;
