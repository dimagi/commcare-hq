DROP FUNCTION IF EXISTS write_blob_bucket(UUID, TEXT);

CREATE FUNCTION write_blob_bucket(
    p_attachment_id UUID, p_blob_bucket TEXT
) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_form_id, 'siphash24');
$$ LANGUAGE plproxy;
