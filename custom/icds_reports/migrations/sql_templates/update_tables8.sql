ALTER TABLE awc_location ADD COLUMN aggregation_level integer;
CREATE INDEX awc_location_indx1 ON awc_location (aggregation_level)