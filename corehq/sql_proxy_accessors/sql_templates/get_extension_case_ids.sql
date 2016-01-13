DROP FUNCTION IF EXISTS get_extension_case_ids(TEXT, TEXT[]);

CREATE FUNCTION get_extension_case_ids(domain_name TEXT, owner_ids TEXT[]) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
