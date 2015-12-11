DROP FUNCTION IF EXISTS get_form_operations(TEXT);

CREATE FUNCTION get_form_operations(form_id TEXT) RETURNS SETOF form_processor_xformoperationsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
