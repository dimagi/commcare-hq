DROP FUNCTION IF EXISTS get_form_by_id(TEXT);

CREATE FUNCTION get_form_by_id(form_id TEXT) RETURNS SETOF form_processor_xforminstancesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
