DROP FUNCTION IF EXISTS get_case_form_ids(TEXT);

CREATE FUNCTION get_case_form_ids(case_id TEXT) RETURNS TABLE (form_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;
