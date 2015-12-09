DROP FUNCTION IF EXISTS delete_test_forms(TEXT, TEXT);

-- RUN ON ALL must return SETOF
CREATE FUNCTION delete_test_forms(domain_name TEXT, user_id TEXT) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
