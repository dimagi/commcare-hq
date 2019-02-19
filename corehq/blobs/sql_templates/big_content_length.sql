ALTER TABLE blobs_blobmeta ADD COLUMN big_content_length BIGINT;

UPDATE blobs_blobmeta SET big_content_length = content_length;

ALTER TABLE blobs_blobmeta ALTER COLUMN big_content_length SET NOT NULL;
ALTER TABLE blobs_blobmeta DROP COLUMN content_length;
ALTER TABLE blobs_blobmeta RENAME COLUMN big_content_length TO content_length;
