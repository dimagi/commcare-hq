-- Schema containing functions shared by all domains' ProjectDB tables

CREATE SCHEMA IF NOT EXISTS lib_projectdb;
GRANT USAGE ON SCHEMA lib_projectdb TO PUBLIC;

CREATE OR REPLACE FUNCTION lib_projectdb.coerce_to_date(value text)
RETURNS date
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  IF left(value, 10) !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
    RETURN NULL;
  END IF;
  RETURN left(value, 10)::date;
EXCEPTION
  WHEN datetime_field_overflow OR invalid_datetime_format THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION lib_projectdb.coerce_to_number(value text)
RETURNS numeric
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  RETURN value::numeric;
EXCEPTION
  WHEN invalid_text_representation OR numeric_value_out_of_range THEN
    RETURN NULL;
END;
$$;
