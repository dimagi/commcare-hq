CREATE OR REPLACE FUNCTION get_expired_blobs(
    TIMESTAMP WITH TIME ZONE,
    INTEGER
) RETURNS SETOF blobs_blobmeta AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM blobs_blobmeta
    WHERE expires_on IS NOT NULL AND expires_on < $1 LIMIT $2;
END
$$ LANGUAGE plpgsql;
