DROP FUNCTION IF EXISTS get_form_ids_by_type_and_date(text, text, INTEGER);

CREATE FUNCTION get_form_ids_by_type_and_date(
    start_date timestamp without time zone,
    end_date timestamp without time zone,
    state INTEGER DEFAULT 1,
    )
    RETURNS SETOF form_processor_xforminstancesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
