ALTER TABLE awc_location ADD COLUMN aggregation_level integer;
CREATE INDEX awc_location_indx1 ON awc_location (aggregation_level);
CREATE INDEX awc_location_indx2 ON awc_location (state_id);
CREATE INDEX awc_location_indx3 ON awc_location (district_id);
CREATE INDEX awc_location_indx4 ON awc_location (block_id);
CREATE INDEX awc_location_indx5 ON awc_location (supervisor_id);
CREATE INDEX awc_location_indx6 ON awc_location (doc_id);

UPDATE awc_location SET aggregation_level=5 WHERE doc_id != 'All';
UPDATE awc_location SET aggregation_level=4 WHERE supervisor_id != 'All' and doc_id = 'All';
UPDATE awc_location SET aggregation_level=3 WHERE block_id != 'All' and supervisor_id = 'All' and doc_id = 'All';
UPDATE awc_location SET aggregation_level=2 WHERE district_id != 'All' and block_id = 'All' and supervisor_id = 'All' and doc_id = 'All';
UPDATE awc_location SET aggregation_level=1 WHERE state_id != 'All' and district_id = 'All' and block_id = 'All' and supervisor_id = 'All' and doc_id = 'All';

ALTER TABLE agg_child_health ADD COLUMN aggregation_level integer;
ALTER TABLE agg_ccs_record ADD COLUMN aggregation_level integer;
ALTER TABLE agg_awc ADD COLUMN aggregation_level integer;

-- Iterate and add new indexes on the tables
CREATE OR REPLACE FUNCTION agg_child_health_update8() RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
BEGIN
	-- Iterate through partioned tables
	FOR _tablename IN
		SELECT
			child.relname AS child
		FROM pg_inherits
			JOIN pg_class parent	ON pg_inherits.inhparent = parent.oid
			JOIN pg_class child	ON pg_inherits.inhrelid   = child.oid
			JOIN pg_namespace nmsp_parent	ON nmsp_parent.oid  = parent.relnamespace
			JOIN pg_namespace nmsp_child	ON nmsp_child.oid   = child.relnamespace
		WHERE parent.relname='agg_child_health' LOOP

		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx12');
		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx13');
		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx14');
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx12') || ' ON ' || quote_ident(_tablename) || '(district_id)';
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx13') || ' ON ' || quote_ident(_tablename) || '(state_id)';
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx14') || ' ON ' || quote_ident(_tablename) || '(aggregation_level)';
	END LOOP;
	UPDATE agg_child_health SET aggregation_level=5 WHERE awc_id != 'All';
	UPDATE agg_child_health SET aggregation_level=4 WHERE supervisor_id != 'All' and awc_id = 'All';
	UPDATE agg_child_health SET aggregation_level=3 WHERE block_id != 'All' and supervisor_id = 'All' and awc_id = 'All';
	UPDATE agg_child_health SET aggregation_level=2 WHERE district_id != 'All' and block_id = 'All' and supervisor_id = 'All' and awc_id = 'All';
	UPDATE agg_child_health SET aggregation_level=1 WHERE state_id != 'All' and district_id = 'All' and block_id = 'All' and supervisor_id = 'All' and awc_id = 'All';
END;
$BODY$
LANGUAGE plpgsql;
SELECT agg_child_health_update8();
DROP FUNCTION agg_child_health_update8();

CREATE OR REPLACE FUNCTION agg_ccs_record_update8() RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
BEGIN
	-- Iterate through partioned tables
	FOR _tablename IN
		SELECT
			child.relname AS child
		FROM pg_inherits
			JOIN pg_class parent	ON pg_inherits.inhparent = parent.oid
			JOIN pg_class child	ON pg_inherits.inhrelid   = child.oid
			JOIN pg_namespace nmsp_parent	ON nmsp_parent.oid  = parent.relnamespace
			JOIN pg_namespace nmsp_child	ON nmsp_child.oid   = child.relnamespace
		WHERE parent.relname='agg_ccs_record' LOOP

		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx12');
		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx13');
		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx14');
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx12') || ' ON ' || quote_ident(_tablename) || '(district_id)';
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx13') || ' ON ' || quote_ident(_tablename) || '(state_id)';
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx14') || ' ON ' || quote_ident(_tablename) || '(aggregation_level)';
	END LOOP;
	UPDATE agg_ccs_record SET aggregation_level=5 WHERE awc_id != 'All';
	UPDATE agg_ccs_record SET aggregation_level=4 WHERE supervisor_id != 'All' and awc_id = 'All';
	UPDATE agg_ccs_record SET aggregation_level=3 WHERE block_id != 'All' and supervisor_id = 'All' and awc_id = 'All';
	UPDATE agg_ccs_record SET aggregation_level=2 WHERE district_id != 'All' and block_id = 'All' and supervisor_id = 'All' and awc_id = 'All';
	UPDATE agg_ccs_record SET aggregation_level=1 WHERE state_id != 'All' and district_id = 'All' and block_id = 'All' and supervisor_id = 'All' and awc_id = 'All';
END;
$BODY$
LANGUAGE plpgsql;
SELECT agg_ccs_record_update8();
DROP FUNCTION agg_ccs_record_update8();

CREATE OR REPLACE FUNCTION agg_awc_update8() RETURNS VOID AS
$BODY$
DECLARE
	_tablename text;
BEGIN
	-- Iterate through partioned tables
	FOR _tablename IN
		SELECT
			child.relname AS child
		FROM pg_inherits
			JOIN pg_class parent	ON pg_inherits.inhparent = parent.oid
			JOIN pg_class child	ON pg_inherits.inhrelid   = child.oid
			JOIN pg_namespace nmsp_parent	ON nmsp_parent.oid  = parent.relnamespace
			JOIN pg_namespace nmsp_child	ON nmsp_child.oid   = child.relnamespace
		WHERE parent.relname='agg_awc' LOOP

		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx12');
		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx13');
		EXECUTE 'DROP INDEX IF EXISTS' || quote_ident(_tablename || '_indx14');
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx12') || ' ON ' || quote_ident(_tablename) || '(district_id)';
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx13') || ' ON ' || quote_ident(_tablename) || '(state_id)';
		EXECUTE 'CREATE INDEX ' || quote_ident(_tablename || '_indx14') || ' ON ' || quote_ident(_tablename) || '(aggregation_level)';
	END LOOP;
	UPDATE agg_awc SET aggregation_level=5 WHERE awc_id != 'All';
	UPDATE agg_awc SET aggregation_level=4 WHERE supervisor_id != 'All' and awc_id = 'All';
	UPDATE agg_awc SET aggregation_level=3 WHERE block_id != 'All' and supervisor_id = 'All' and awc_id = 'All';
	UPDATE agg_awc SET aggregation_level=2 WHERE district_id != 'All' and block_id = 'All' and supervisor_id = 'All' and awc_id = 'All';
	UPDATE agg_awc SET aggregation_level=1 WHERE state_id != 'All' and district_id = 'All' and block_id = 'All' and supervisor_id = 'All' and awc_id = 'All';
END;
$BODY$
LANGUAGE plpgsql;
SELECT agg_awc_update8();
DROP FUNCTION agg_awc_update8();