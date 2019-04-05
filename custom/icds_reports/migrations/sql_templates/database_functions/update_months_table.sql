-- Update months table
CREATE OR REPLACE FUNCTION update_months_table(date) RETURNS void AS
$BODY$
BEGIN
    INSERT INTO "icds_months" (month_name, start_date, end_date)
  SELECT
    to_char($1, 'Mon YYYY'),
    date_trunc('MONTH', $1)::DATE,
    (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 day')::DATE
  WHERE NOT EXISTS (SELECT 1 FROM "icds_months" WHERE start_date=date_trunc('MONTH', $1)::DATE);
  TRUNCATE TABLE "icds_months_local";
  CREATE TEMPORARY TABLE "tmp_months_local" AS SELECT * FROM "icds_months";
  INSERT INTO "icds_months_local" SELECT * FROM "tmp_months_local";
  DROP TABLE "tmp_months_local";
END;
$BODY$
LANGUAGE plpgsql;
