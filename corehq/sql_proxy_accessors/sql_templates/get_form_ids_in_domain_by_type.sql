DROP FUNCTION IF EXISTS get_form_ids_in_domain_by_type(TEXT, INTEGER);

CREATE FUNCTION get_form_ids_in_domain_by_type(domain_name TEXT, p_state INTEGER DEFAULT 1) RETURNS TABLE (form_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
