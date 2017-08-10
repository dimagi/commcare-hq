DROP FUNCTION IF EXISTS get_location_level_id(INT, INT, INT, INT, INT, INT, INT, INT, INT);

CREATE FUNCTION get_location_level_id(level INT, loc_0 INT, loc_1 INT,
                                      loc_2 INT, loc_3 INT, loc_4 INT,
                                      loc_5 INT, loc_6 INT, loc_7 INT) RETURNS INT AS $$
DECLARE
  ids TEXT[] := ARRAY[loc_0, loc_1, loc_2, loc_3, loc_4, loc_5, loc_6, loc_7];
  loc_level INT := (
        CASE WHEN loc_0 IS NULL THEN 0 ELSE 1 END +
        CASE WHEN loc_1 IS NULL THEN 0 ELSE 1 END +
        CASE WHEN loc_2 IS NULL THEN 0 ELSE 1 END +
        CASE WHEN loc_3 IS NULL THEN 0 ELSE 1 END +
        CASE WHEN loc_4 IS NULL THEN 0 ELSE 1 END +
        CASE WHEN loc_5 IS NULL THEN 0 ELSE 1 END +
        CASE WHEN loc_6 IS NULL THEN 0 ELSE 1 END +
        CASE WHEN loc_7 IS NULL THEN 0 ELSE 1 END
    );
BEGIN
  -- Note that lists in plpgsql are 1 indexed not 0 indexed
  RETURN CASE WHEN level >= loc_level THEN NULL ELSE ids[loc_level - level] END;
END;
$$ LANGUAGE plpgsql;
