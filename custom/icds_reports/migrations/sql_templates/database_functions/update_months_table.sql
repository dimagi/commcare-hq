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

  INSERT INTO "icds_months_local" (month_name, start_date, end_date)
  SELECT
    to_char($1, 'Mon YYYY'),
    date_trunc('MONTH', $1)::DATE,
    (date_trunc('MONTH', $1) + INTERVAL '1 MONTH - 1 day')::DATE
  WHERE NOT EXISTS (SELECT 1 FROM "icds_months_local" WHERE start_date=date_trunc('MONTH', $1)::DATE);
END;
$BODY$
LANGUAGE plpgsql;
