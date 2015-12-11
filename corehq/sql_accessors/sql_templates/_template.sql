-- drop it first in case we're changing the signature in which case 'CREATE OR REPLACE' will fail
DROP FUNCTION IF EXISTS function_name(TEXT);

-- return SETOF so that we get 0 rows when no form matches otherwise we'll get an empty row
CREATE FUNCTION function_name(args TEXT) RETURNS SETOF tablename AS $$
BEGIN
    -- run query here
    -- e.g. SELECT * FROM tablename where column = $1;
END;
$$ LANGUAGE plpgsql;
