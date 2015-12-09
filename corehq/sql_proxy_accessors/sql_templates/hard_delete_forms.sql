DROP FUNCTION IF EXISTS hard_delete_forms(TEXT, TEXT[]);

CREATE FUNCTION hard_delete_forms(domain_name TEXT, form_ids TEXT[]) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT form_ids;
    RUN ON hash_string(form_ids, 'siphash24');
$$ LANGUAGE plproxy;
