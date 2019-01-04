DROP TRIGGER blobs_blobmeta_trigger ON blobs_blobmeta;
DROP FUNCTION mutate_blobs_blobmeta();
DROP VIEW blobs_blobmeta;
ALTER TABLE blobs_blobmeta_tbl RENAME TO blobs_blobmeta;
