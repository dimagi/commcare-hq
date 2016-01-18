CREATE OR REPLACE FUNCTION case_notify() RETURNS trigger AS $$
DECLARE
BEGIN
  PERFORM pg_notify('{{ channel.name }}', row_to_json(NEW));
  RETURN NEW;
END;
$$ LANGUAGE plproxy;

CREATE TRIGGER case_insert_notify AFTER UPDATE ON {{ case_table }} FOR EACH ROW EXECUTE PROCEDURE case_notify();
