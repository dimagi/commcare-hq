DROP FUNCTION IF EXISTS get_all_reverse_indices(TEXT, TEXT[]);

CREATE FUNCTION get_all_reverse_indices(domain_name TEXT, case_ids TEXT[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
