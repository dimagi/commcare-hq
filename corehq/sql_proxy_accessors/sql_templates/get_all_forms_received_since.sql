DROP FUNCTION IF EXISTS get_all_forms_received_since(timestamp with time zone, integer);

CREATE FUNCTION get_all_forms_received_since(reference_date timestamp with time zone, query_limit integer)
RETURNS SETOF form_processor_xforminstancesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
