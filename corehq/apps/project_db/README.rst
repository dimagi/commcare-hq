Project DB
==========

Project DB provides auto-generated PostgreSQL tables for CommCare case data.
Each domain gets its own PostgreSQL schema containing one table per case type,
with columns derived from the data dictionary. The aim is a relational, typed
representation of case data that supports JOINs across case types without any
project-specific configuration.

Layout
------

- One schema per domain, named ``projectdb_<domain>``.
- One table per case type, named after the case type.
- Each table has a fixed set of columns mirroring ``CommCareCase``, plus a
  ``prop__<name>`` column for every case property (defaults to `''`). Typed
  properties (date, number, select, gps) get an additional typed column, e.g.
  ``date_prop__<name>``. GPS properties are stored as the earthdistance
  ``earth`` type, which requires the ``cube`` and ``earthdistance`` extensions.

Postgres truncates identifiers at 63 bytes, so schema, table, and column names
are truncated with a hash suffix for uniqueness, with the raw values stored as
postgresql comments so they can be recovered on inspection.

Definitions are built with `SQLAlchemy Core
<https://docs.sqlalchemy.org/en/13/core/>`_ and live in the database configured
for the ``project_db`` engine (the default database unless
``REPORTING_DATABASES`` maps it elsewhere).

Evolution
---------

Tables are created and synced automatically as the data dictionary is modified.
Provisioning is append-only and idempotent: a domain's schema and tables are
created if absent, and new columns and indexes are added, but existing ones are
never dropped or rewritten. A new case property becomes a new column; a new
case type becomes a new table.

Access control
--------------

Each domain gets a read-only Postgres role named after its schema with access
to only that schema. Queries connect as that role, so Postgres refuses to read
another domain's tables however the query is written. This is a
belt-and-suspenders backstop for the query layer, which shouldn't allow that
sort of access anyways. Table definition and population connect as the owner
instead, since the domain role cannot write.

HQ's database user cannot create roles, so provisioning goes through
``projectdb_provision_role`` and ``projectdb_drop_role``, ``SECURITY DEFINER``
functions that run as their owner. commcare-cloud installs these in production;
``project_db_setup.sql`` mirrors that template for dev and CI, where
``setup_project_db`` applies it.

Status
------

Turning on the ``PROJECT_DB`` feature flag sets up the tables for the domain,
and thereafter they stay in sync automatically when the data dictionary is
modified.  New cases are sychronously sent to the ProjectDB during form
submission.  Pre-existing cases must be manually back-populated using
``manage_project_db --populate``

TODOs
----

- Wire schema cleanup to domain deletion. ``DomainSchema.drop`` exists but
  is not registered in ``corehq/apps/domain/deletion.py``. Because this is a raw
  Postgres schema rather than a Django model, the standard model-based
  registration won't catch it; deleting a domain would orphan its
  ``projectdb_<domain>`` schema, data, and role.
- Use the stored property-name comments when populating. Each property column
  stores its raw case property name as a Postgres comment, which lets the
  source property be recovered by inspecting the table. ``case_to_row`` could
  use this to iterate through columns instead of properties.
- Date vs Datetime. Looks like the DD only supports date
  properties, not datetime - does it intend the latter? Should we
  support both?
- Index external ID.
- Put limit on number of property columns
- Set up automatic update call on data dictionary change, and auto population
  on case update
- Add a SQL user per domain with only access to that domain's schema
