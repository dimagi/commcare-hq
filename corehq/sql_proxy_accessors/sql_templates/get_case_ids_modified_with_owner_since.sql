DROP FUNCTION IF EXISTS get_case_ids_modified_with_owner_since(TEXT, TEXT, TIMESTAMP WITH TIME ZONE);

CREATE FUNCTION get_case_ids_modified_with_owner_since(domain_name TEXT, p_owner_id TEXT, reference_date TIMESTAMP WITH TIME ZONE)
RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
