DROP FUNCTION IF EXISTS get_reverse_indexed_cases_3(TEXT, TEXT[]);

CREATE FUNCTION get_reverse_indexed_cases_3(
    domain_name TEXT,
    case_ids TEXT[],
    case_types TEXT[] DEFAULT NULL,
    p_closed BOOLEAN DEFAULT NULL
) RETURNS SETOF form_processor_commcarecasesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
