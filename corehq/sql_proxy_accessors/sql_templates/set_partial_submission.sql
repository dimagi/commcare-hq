DROP FUNCTION IF EXISTS set_partial_submission(TEXT);

CREATE FUNCTION set_partial_submission(form_id TEXT) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
