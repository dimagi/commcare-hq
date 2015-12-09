DROP FUNCTION IF EXISTS hard_delete_cases(TEXT, TEXT[]);

CREATE FUNCTION hard_delete_cases(domain_name TEXT, case_ids TEXT[]) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
