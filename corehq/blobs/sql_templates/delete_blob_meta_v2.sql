CREATE OR REPLACE FUNCTION delete_blob_meta(TEXT) RETURNS SETOF BIGINT AS $$
BEGIN
    RETURN QUERY WITH deleted AS (
        DELETE FROM blobs_blobmeta
        WHERE "key" = $1
        RETURNING *
    ), ins AS (
        INSERT INTO blobs_deletedblobmeta (
            "id",
            "domain",
            "parent_id",
            "name",
            "key",
            "type_code",
            "created_on",
            "deleted_on"
        )
        SELECT
            "id",
            "domain",
            "parent_id",
            "name",
            "key",
            "type_code",
            "created_on",
            NOW() AT TIME ZONE 'UTC'
        FROM deleted
        WHERE expires_on IS NULL
    ) SELECT COUNT(*) FROM deleted;
END
$$ LANGUAGE plpgsql;
