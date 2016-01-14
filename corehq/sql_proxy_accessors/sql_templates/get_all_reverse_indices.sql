DROP FUNCTION IF EXISTS get_all_reverse_indices(TEST[]);

CREATE FUNCTION get_all_reverse_indices(case_ids TEXT[]) RETURNS SETOF form_processor_commcarecaseindexsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
