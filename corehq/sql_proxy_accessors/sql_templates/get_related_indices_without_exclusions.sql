DROP FUNCTION IF EXISTS get_related_indices(TEXT, TEXT[]);

CREATE FUNCTION get_related_indices(
    domain_name TEXT,
    case_ids_array TEXT[]
) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;  -- cannot SPLIT case_ids_array because of join on referenced_id
$$ LANGUAGE plproxy;
