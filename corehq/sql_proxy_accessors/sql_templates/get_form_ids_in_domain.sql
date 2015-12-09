DROP FUNCTION IF EXISTS get_form_ids_in_domain(TEXT, TEXT);

CREATE FUNCTION get_form_ids_in_domain(domain_name TEXT, user_id TEXT) RETURNS TABLE (form_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
