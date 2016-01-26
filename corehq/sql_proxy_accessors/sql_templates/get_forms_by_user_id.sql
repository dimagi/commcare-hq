DROP FUNCTION IF EXISTS get_forms_by_user_id(TEXT, TEXT, INTEGER);

CREATE FUNCTION get_forms_by_user_id(domain TEXT, user_id TEXT, state INTEGER) RETURNS SETOF form_processor_xforminstancesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
