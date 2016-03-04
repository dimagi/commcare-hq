DROP FUNCTION IF EXISTS soft_undelete_cases(TEXT, TEXT[]);

CREATE FUNCTION soft_undelete_cases(
    p_domain TEXT,
    case_ids TEXT[]) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
