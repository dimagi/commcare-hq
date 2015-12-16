DROP FUNCTION IF EXISTS get_case_indices(TEXT);

CREATE FUNCTION get_case_indices(case_id TEXT) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;
