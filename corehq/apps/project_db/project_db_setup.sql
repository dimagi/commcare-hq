-- Set up the extensions and functions ProjectDB depends on.
-- Production environments apply this via commcare-cloud, in
-- postgresql_base/templates/project_db_setup.sql.j2.  This mirrors it in dev/test.

CREATE EXTENSION IF NOT EXISTS cube;  -- Provides `cube` type needed by earthdistance
CREATE EXTENSION IF NOT EXISTS earthdistance;  -- `earth` column type and associated geopoint distance calculations
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- trigram-based similarity() function for fuzzy search
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;  -- phonetic match dmetaphone() function, also soundex and levenshtein
