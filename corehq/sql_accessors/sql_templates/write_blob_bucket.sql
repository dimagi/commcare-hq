DROP FUNCTION IF EXISTS write_blob_bucket(TEXT, UUID, TEXT);

CREATE FUNCTION write_blob_bucket(
    p_form_id TEXT, p_attachment_id UUID, p_blob_bucket TEXT
) RETURNS VOID AS $$
BEGIN
    UPDATE form_processor_xformattachmentsql SET
        blob_bucket = p_blob_bucket
    WHERE attachment_id = p_attachment_id;
END $$
LANGUAGE 'plpgsql';
