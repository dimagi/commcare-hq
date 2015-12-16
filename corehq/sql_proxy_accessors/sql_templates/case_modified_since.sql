DROP FUNCTION IF EXISTS case_modified_since(TEXT, TIMESTAMP);

CREATE FUNCTION case_modified_since(case_id TEXT, server_modified_on TIMESTAMP, case_modified OUT BOOLEAN) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;
