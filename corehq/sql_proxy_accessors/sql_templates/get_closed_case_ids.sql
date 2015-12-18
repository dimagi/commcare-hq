DROP FUNCTION IF EXISTS get_closed_case_ids(TEXT, TEXT);
get_open_case_ids.sql
CREATE FUNCTION get_closed_case_ids(domain_name TEXT, p_owner_id TEXT) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
