DROP FUNCTION IF EXISTS filter_open_case_ids(TEXT, TEXT[]);

CREATE FUNCTION filter_open_case_ids(
    domain_name TEXT,
    case_ids_array TEXT[]
) RETURNS TABLE (case_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids_array;
    RUN ON hash_string(case_ids_array, 'siphash24');
$$ LANGUAGE plproxy;
