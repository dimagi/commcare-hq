DROP FUNCTION IF EXISTS get_case_ids_in_domain(TEXT, TEXT);

CREATE FUNCTION get_case_ids_in_domain(domain_name TEXT, case_type TEXT DEFAULT NULL) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
