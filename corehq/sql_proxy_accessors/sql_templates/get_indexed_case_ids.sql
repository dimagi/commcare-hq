DROP FUNCTION IF EXISTS get_indexed_case_ids(TEXT, TEXT[]);

CREATE FUNCTION get_indexed_case_ids(domain_name TEXT, case_ids TEXT[])
RETURNS TABLE (referenced_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
