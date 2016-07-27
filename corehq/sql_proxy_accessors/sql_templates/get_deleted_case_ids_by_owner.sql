DROP FUNCTION IF EXISTS get_deleted_case_ids_by_owner(TEXT, TEXT);

CREATE FUNCTION get_deleted_case_ids_by_owner(domain_name TEXT, p_owner_id TEXT) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
