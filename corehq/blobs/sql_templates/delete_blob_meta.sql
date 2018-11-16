CREATE OR REPLACE FUNCTION delete_blob_meta(TEXT) RETURNS SETOF BIGINT AS $$
BEGIN
    RETURN QUERY WITH deleted AS (
        DELETE FROM blobs_blobmeta WHERE "key" = $1 RETURNING *
    ) SELECT COUNT(*) FROM deleted;
END
$$ LANGUAGE plpgsql;
