ALTER TABLE awc_location ADD COLUMN aggregation_level integer;
CREATE INDEX awc_location_indx1 ON awc_location (aggregation_level);
CREATE INDEX awc_location_indx2 ON awc_location (state_id);
CREATE INDEX awc_location_indx3 ON awc_location (district_id);
CREATE INDEX awc_location_indx4 ON awc_location (block_id);
CREATE INDEX awc_location_indx5 ON awc_location (supervisor_id);
CREATE INDEX awc_location_indx6 ON awc_location (doc_id);