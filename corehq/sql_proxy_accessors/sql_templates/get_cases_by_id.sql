DROP FUNCTION IF EXISTS get_cases_by_id(TEXT[]);

CREATE FUNCTION get_cases_by_id(case_ids TEXT[]) RETURNS SETOF form_processor_commcarecasesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
