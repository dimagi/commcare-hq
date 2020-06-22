CREATE UNLOGGED TABLE "tmp_ls_usage" AS SELECT
    supervisor_id,
    count(*) as form_count
    FROM "{ls_usage_ucr}" ls_usage_ucr
    WHERE timeend<'{next_month_start}'
    GROUP BY supervisor_id;

UPDATE "{tablename}" agg_ls
    SET num_supervisor_launched = CASE WHEN form_count>0 THEN 1 ELSE 0 END
    from (
        SELECT
            supervisor_id,
            form_count
        FROM tmp_ls_usage
        ) ut
        WHERE agg_ls.supervisor_id = ut.supervisor_id;

DROP TABLE "tmp_ls_usage";
