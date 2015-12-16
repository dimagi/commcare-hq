DROP FUNCTION IF EXISTS delete_all_cases(TEXT);

-- RUN ON ALL must return SETOF
CREATE FUNCTION delete_all_cases(domain_name TEXT) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
