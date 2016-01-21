DROP FUNCTION IF EXISTS get_forms_by_user_id(TEXT);

CREATE FUNCTION get_forms_by_user_id(user_id TEXT) RETURNS SETOF form_processor_xforminstancesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
