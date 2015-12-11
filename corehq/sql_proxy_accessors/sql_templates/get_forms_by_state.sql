DROP FUNCTION IF EXISTS get_forms_by_state(TEXT, INTEGER, INTEGER, BOOLEAN);

CREATE FUNCTION get_forms_by_state(
    domain_name TEXT,
    state INTEGER,
    limit_to INTEGER,
    recent_first BOOLEAN DEFAULT TRUE
    )
    RETURNS SETOF form_processor_xforminstancesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
