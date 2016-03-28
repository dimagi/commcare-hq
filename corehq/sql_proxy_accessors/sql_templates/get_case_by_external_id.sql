DROP FUNCTION IF EXISTS get_case_by_external_id(TEXT, TEXT, TEXT);

CREATE FUNCTION get_case_by_external_id(p_domain TEXT, p_external_id TEXT, p_type TEXT DEFAULT NULL) RETURNS SETOF form_processor_commcarecasesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
