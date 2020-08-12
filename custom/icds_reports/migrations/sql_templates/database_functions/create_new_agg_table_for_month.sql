-- Create new aggregate month tables
CREATE OR REPLACE FUNCTION create_new_aggregate_table_for_month(text, date) RETURNS VOID AS
$BODY$
DECLARE
  _tablename text;
  _tablename1 text;
  _tablename2 text;
  _tablename3 text;
  _tablename4 text;
  _tablename5 text;
BEGIN
  -- This is for cleaning up old style non-aggregation level partioned tables
  _tablename := $1 || '_' || (date_trunc('MONTH', $2)::DATE);
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename);

  _tablename1 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_1';
  _tablename2 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_2';
  _tablename3 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_3';
  _tablename4 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_4';
  _tablename5 := $1 || '_' || (date_trunc('MONTH', $2)::DATE) || '_5';
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename1);
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename2);
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename3);
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename4);
  EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_tablename5);

  EXECUTE 'CREATE TABLE ' || quote_ident(_tablename1) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 1)' ||
      ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename2) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 2)' ||
      ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename3) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 3)' ||
      ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename4) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 4)' ||
      ') INHERITS ('  || quote_ident($1) || ')';
    EXECUTE 'CREATE TABLE ' || quote_ident(_tablename5) || '(' ||
        'CHECK ( month = DATE ' || quote_literal(date_trunc('MONTH', $2)::DATE) || ' AND aggregation_level = 5)' ||
      ') INHERITS ('  || quote_ident($1) || ')';
END;
$BODY$
LANGUAGE plpgsql;
