DROP FUNCTION IF EXISTS get_case_ids_in_domain_by_owners(TEXT, TEXT[]);

CREATE FUNCTION get_case_ids_in_domain_by_owners(domain_name TEXT, owner_ids TEXT[]) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
