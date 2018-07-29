-- Create new month tables
CREATE OR REPLACE FUNCTION create_new_table_for_month(text, date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename text;
BEGIN
  _tablename := $1 || '_' || (date_trunc('MONTH', $2)::DATE);
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename);
  EXECUTE 'CREATE TABLE ' || quote_ident(_tablename) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' )' ||
      ') INHERITS ('  || quote_ident($1) || ')';
END;
$BODY$
LANGUAGE plpgsql;