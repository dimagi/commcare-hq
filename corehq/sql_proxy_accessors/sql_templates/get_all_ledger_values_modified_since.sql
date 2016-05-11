DROP FUNCTION IF EXISTS get_all_ledger_values_modified_since(timestamp with time zone, integer);

CREATE FUNCTION get_all_ledger_values_modified_since(reference_date timestamp with time zone, query_limit integer)
RETURNS SETOF form_processor_ledgervalue AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
