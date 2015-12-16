DROP FUNCTION IF EXISTS get_case_by_id(TEXT);

CREATE FUNCTION get_case_by_id(case_id TEXT) RETURNS SETOF form_processor_commcarecasesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;
