DROP FUNCTION IF EXISTS compare_server_client_case_transaction_order(TEXT);

CREATE FUNCTION compare_server_client_case_transaction_order(case_id TEXT) RETURNS BOOLEAN AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;
