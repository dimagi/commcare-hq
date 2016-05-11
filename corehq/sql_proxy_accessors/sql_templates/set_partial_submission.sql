DROP FUNCTION IF EXISTS set_partial_submission(TEXT);

CREATE FUNCTION set_partial_submission(p_form_id TEXT) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_form_id, 'siphash24');
$$ LANGUAGE plproxy;
