DROP FUNCTION IF EXISTS get_reverse_indexed_cases(TEXT, TEXT[]);

CREATE FUNCTION get_reverse_indexed_cases(domain_name TEXT, case_ids TEXT[]) RETURNS SETOF form_processor_commcarecasesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
