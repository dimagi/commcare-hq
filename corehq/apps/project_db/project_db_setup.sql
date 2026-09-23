-- Set up the extensions, functions, and privileges ProjectDB depends on.
-- Production environments apply this via commcare-cloud, in
-- postgresql_base/templates/project_db_setup.sql.j2.  This mirrors it in dev/test.

CREATE EXTENSION IF NOT EXISTS cube;  -- Provides `cube` type needed by earthdistance
CREATE EXTENSION IF NOT EXISTS earthdistance;  -- `earth` column type and associated geopoint distance calculations
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- trigram-based similarity() function for fuzzy search
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;  -- phonetic match dmetaphone() function, also soundex and levenshtein

-- RDS doesn't expose pg_authid, create our own stand-in
-- Dev/test never reads it (no pgbouncer here), but the provisioning
-- functions are shared with prod, so it has to exist for them to write to.
CREATE SCHEMA IF NOT EXISTS pgbouncer;
CREATE TABLE IF NOT EXISTS pgbouncer.project_db_passwords (
    rolname text PRIMARY KEY,
    passwd text NOT NULL
);
REVOKE ALL ON pgbouncer.project_db_passwords FROM PUBLIC;

-- In production environments, we can't create roles directly, so we need
-- SECURITY DEFINER functions, which run with their owner's permission. In
-- prod these are provisioned during db setup with superuser access.
CREATE OR REPLACE FUNCTION projectdb_provision_role(role_name text, role_password text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  IF role_name NOT LIKE 'projectdb\_%' THEN
    RAISE EXCEPTION 'refusing to manage role %', role_name;
  END IF;
  EXECUTE format('CREATE ROLE %I WITH LOGIN PASSWORD %L', role_name, role_password);
  EXECUTE format('GRANT %I TO %I', role_name, current_user);
  INSERT INTO pgbouncer.project_db_passwords (rolname, passwd)
  VALUES (role_name, role_password);
EXCEPTION WHEN duplicate_object THEN
  -- Role already exists. Membership was granted when it was first created
  EXECUTE format('ALTER ROLE %I WITH PASSWORD %L', role_name, role_password);
  INSERT INTO pgbouncer.project_db_passwords (rolname, passwd)
  VALUES (role_name, role_password)
  ON CONFLICT (rolname) DO UPDATE SET passwd = EXCLUDED.passwd;
END;
$$;

CREATE OR REPLACE FUNCTION projectdb_drop_role(role_name text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  IF role_name NOT LIKE 'projectdb\_%' THEN
    RAISE EXCEPTION 'refusing to manage role %', role_name;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
    -- drop grants to the role, which would otherwise block DROP ROLE
    EXECUTE format('DROP OWNED BY %I', role_name);
    EXECUTE format('DROP ROLE %I', role_name);
  END IF;
  DELETE FROM pgbouncer.project_db_passwords WHERE rolname = role_name;
END;
$$;

-- Postgres grants EXECUTE on new functions to PUBLIC by default, which would
-- make these callable by every domain role.  Production also grants EXECUTE to
-- HQ's user; here HQ's user owns the functions, so it already has it.
REVOKE EXECUTE ON FUNCTION projectdb_provision_role(text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION projectdb_drop_role(text) FROM PUBLIC;

-- Postgres 14 grants CREATE on the public schema to PUBLIC, 15+ don't.  USAGE
-- is deliberately left in place so domain roles can still call the functions
-- installed by the extensions above.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
