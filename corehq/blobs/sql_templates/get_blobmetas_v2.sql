CREATE OR REPLACE FUNCTION get_blobmetas(
    parent_ids TEXT[],
    type_code_ SMALLINT
) RETURNS SETOF blobs_blobmeta AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM blobs_blobmeta
    WHERE parent_id = ANY(parent_ids) AND deleted_on IS NULL AND (
        type_code_ IS NULL OR type_code = type_code_
    );
END;
$$ LANGUAGE plpgsql;
