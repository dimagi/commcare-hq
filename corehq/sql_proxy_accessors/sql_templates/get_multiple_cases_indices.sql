DROP FUNCTION IF EXISTS get_multiple_cases_indices(TEXT[]);

CREATE FUNCTION get_multiple_cases_indices(case_ids TEXT[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
