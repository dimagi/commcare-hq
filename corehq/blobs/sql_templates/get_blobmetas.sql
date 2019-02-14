DROP FUNCTION IF EXISTS get_blobmetas(TEXT[]);
DROP FUNCTION IF EXISTS get_blobmetas(TEXT[], SMALLINT);

CREATE FUNCTION get_blobmetas(
    parent_ids TEXT[],
    type_code_ SMALLINT
) RETURNS SETOF blobs_blobmeta AS $$
BEGIN
    -- order by parent id so that we don't have to do it in python
    RETURN QUERY
    SELECT * FROM blobs_blobmeta
    WHERE parent_id = ANY(parent_ids) AND (
        type_code_ IS NULL OR type_code = type_code_
    );
END;
$$ LANGUAGE plpgsql;
