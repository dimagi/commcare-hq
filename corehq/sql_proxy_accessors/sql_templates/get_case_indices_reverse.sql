DROP FUNCTION IF EXISTS get_case_indices_reverse(TEXT);

CREATE FUNCTION get_case_indices_reverse(case_id TEXT) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
