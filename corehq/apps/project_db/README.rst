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
  ``prop__<name>`` column for every case property. Typed properties (date,
  number) get an additional coerced column, e.g. ``prop__<name>__date``.

Definitions are built with `SQLAlchemy Core
<https://docs.sqlalchemy.org/en/13/core/>`_ and live in the database configured
for the ``project_db`` engine (the default database unless
``REPORTING_DATABASES`` maps it elsewhere).

Evolution
---------

Provisioning is **append-only** and idempotent: a domain's schema and tables are
created if absent, and new columns and indexes are added, but existing ones are
never dropped or rewritten. A new case property becomes a new column; a new case
type becomes a new table.

Status
------

This module currently defines and provisions the table structure only.
Populating the tables with case data and querying them are not yet implemented.

TODOs
----

- **Identifier length & collisions.** ``domain`` and ``case_type`` are used
  directly as Postgres identifiers, which are silently truncated at 63 bytes.
  ``CaseProperty.name`` allows up to 255 chars, so generated ``prop__<name>``
  columns can truncate and collide; long domain names can collide on schema
  name, where ``DROP SCHEMA ... CASCADE`` could affect another domain's data.
  Truncate-and-hash before use (see the ``# TODO`` in ``table_ddl.py``).

- **Wire schema cleanup to domain deletion.** ``DomainSchema.drop`` exists but
  is not registered in ``corehq/apps/domain/deletion.py``. Because this is a raw
  Postgres schema rather than a Django model, the standard model-based
  registration won't catch it; deleting a domain would orphan its
  ``projectdb_<domain>`` schema and data.
