DROP FUNCTION IF EXISTS get_blobmetas(TEXT[]);
DROP FUNCTION IF EXISTS get_blobmetas(TEXT[], SMALLINT);

CREATE FUNCTION get_blobmetas(parent_ids TEXT[], type_code_ SMALLINT)
RETURNS SETOF blobs_blobmeta AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT parent_ids;
    RUN ON hash_string(parent_ids, 'siphash24');
$$ LANGUAGE plproxy;
