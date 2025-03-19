DROP FUNCTION IF EXISTS soft_delete_forms_3(TEXT, TEXT[], TIMESTAMP, TEXT);

CREATE FUNCTION soft_delete_forms_3(
    p_domain TEXT,
    form_ids TEXT[],
    deletion_date TIMESTAMP,
    deletion_id TEXT DEFAULT NULL) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT form_ids;
    RUN ON hash_string(form_ids, 'siphash24');
$$ LANGUAGE plproxy;
