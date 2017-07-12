DROP FUNCTION IF EXISTS get_closed_and_deleted_ids(TEXT, TEXT[]);

CREATE FUNCTION get_closed_and_deleted_ids(
    domain_name TEXT,
    case_ids_array TEXT[]
) RETURNS TABLE (case_id VARCHAR(255), closed BOOLEAN, deleted BOOLEAN) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids_array;
    RUN ON hash_string(case_ids_array, 'siphash24');
$$ LANGUAGE plproxy;
