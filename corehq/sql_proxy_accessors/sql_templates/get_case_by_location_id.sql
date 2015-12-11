DROP FUNCTION IF EXISTS get_case_by_location_id(text, text);

CREATE FUNCTION get_case_by_location_id(domain_name text, location_id text) RETURNS SETOF form_processor_commcarecasesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
