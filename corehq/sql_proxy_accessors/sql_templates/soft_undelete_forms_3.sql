DROP FUNCTION IF EXISTS soft_undelete_forms_3(TEXT, TEXT[], TEXT);

CREATE FUNCTION soft_undelete_forms_3(
    p_domain TEXT,
    form_ids TEXT[],
    problem TEXT) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT form_ids;
    RUN ON hash_string(form_ids, 'siphash24');
$$ LANGUAGE plproxy;
