CREATE OR REPLACE FUNCTION delete_blob_meta(TEXT) RETURNS SETOF BIGINT AS $$
BEGIN
    RETURN QUERY WITH updated AS (
        UPDATE blobs_blobmeta
        SET deleted_on = NOW() AT TIME ZONE 'UTC'
        WHERE "key" = $1 AND expires_on IS NULL
        RETURNING "key"
    ), deleted AS (
        DELETE FROM blobs_blobmeta
        WHERE "key" = $1 AND expires_on IS NOT NULL
        RETURNING "key"
    ) SELECT COUNT(*) FROM (
        SELECT * FROM updated
        UNION
        SELECT * FROM deleted
    ) changes;
END
$$ LANGUAGE plpgsql;
