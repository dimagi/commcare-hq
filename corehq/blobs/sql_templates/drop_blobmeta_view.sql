-- Re-create function so it works on the proxy as well as shards
-- which have differing function definitions. For some reason this
-- is necessary, but possibly only on the proxy?

-- temporary function to evaluate a string -> create function
create function tmp_eval(expression text) returns void as
$body$
declare
  result integer;
begin
  execute expression;
end;
$body$ language plpgsql;

-- temporary table holding get_blobmetas source
CREATE TEMPORARY TABLE temp_func_src(src TEXT, lang TEXT);
INSERT INTO temp_func_src (src, lang)
SELECT routine_definition, external_language
FROM information_schema.routines
WHERE specific_schema = 'public' AND routine_name = 'get_blobmetas';

-- do the stuff
DROP TRIGGER blobs_blobmeta_trigger ON blobs_blobmeta;
DROP FUNCTION mutate_blobs_blobmeta();
DROP FUNCTION IF EXISTS get_blobmetas(TEXT[], SMALLINT);
DROP VIEW blobs_blobmeta;
ALTER TABLE blobs_blobmeta_tbl RENAME TO blobs_blobmeta;

-- re-create get_blobmetas function
SELECT tmp_eval(format(
    'CREATE OR REPLACE FUNCTION get_blobmetas(parent_ids TEXT[], ' ||
    'type_code_ SMALLINT) RETURNS SETOF blobs_blobmeta AS $func$ ' ||
    '%s $func$ LANGUAGE %s', src, lang
))
FROM temp_func_src;
