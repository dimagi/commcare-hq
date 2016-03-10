DROP FUNCTION IF EXISTS get_case_types_for_domain(TEXT);

CREATE FUNCTION get_case_types_for_domain(p_domain TEXT) RETURNS TABLE (case_type VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
