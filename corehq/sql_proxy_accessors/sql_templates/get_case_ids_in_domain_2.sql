DROP FUNCTION IF EXISTS get_case_ids_in_domain(TEXT, TEXT, TEXT[], BOOLEAN, BOOLEAN);

CREATE FUNCTION get_case_ids_in_domain(
    domain_name TEXT,
    case_type TEXT DEFAULT NULL,
    owner_ids TEXT[] DEFAULT NULL,
    p_closed BOOLEAN DEFAULT NULL,
    p_deleted BOOLEAN DEFAULT FALSE
) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
