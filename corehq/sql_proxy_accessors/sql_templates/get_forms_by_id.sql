DROP FUNCTION IF EXISTS get_forms_by_id(TEXT[]);

CREATE FUNCTION get_forms_by_id(form_ids TEXT[]) RETURNS SETOF form_processor_xforminstancesql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT form_ids;
    RUN ON hash_string(form_ids, 'siphash24');
$$ LANGUAGE plproxy;
