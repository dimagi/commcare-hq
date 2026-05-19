Project DB
==========

Project DB provides auto-generated PostgreSQL tables for CommCare case data.
Each domain gets a PostgreSQL schema containing one table per case type, with
columns derived from the data dictionary.

This gives a relational, typed representation of case data that supports JOINs
across case types — without any project-specific configuration or management.


How it works
------------

**Schema source**: The data dictionary (``CaseType`` and ``CaseProperty``
models) drives table definitions. No user-facing configuration is needed.

**Implementation layer**: `SQLAlchemy Core
<https://docs.sqlalchemy.org/en/13/core/>`_ for schema definition, DDL, and
query construction.

**Schema layout**: Each domain gets a PostgreSQL schema named
``projectdb_<domain>``. Tables within the schema are named after the case type
(e.g., ``projectdb_myproject.patient``). This means queries can use clean table
names after setting ``search_path``::

    SET LOCAL search_path TO "projectdb_myproject";
    SELECT * FROM patient WHERE prop__dob__date > '2000-01-01';


Table structure
---------------

Every table has the same set of fixed columns derived from
``CommCareCase``:

=============================  =======================  =====
Column                         Type                     Notes
=============================  =======================  =====
``case_id``                    Text                     PK
``owner_id``                   Text                     NOT NULL, indexed
``case_name``                  Text
``opened_on``                  DateTime (tz)
``closed_on``                  DateTime (tz)
``modified_on``                DateTime (tz)            Indexed
``closed``                     Boolean
``external_id``                Text
``server_modified_on``         DateTime (tz)
``parent_id``                  Text                     Indexed
``host_id``                    Text                     Indexed
=============================  =======================  =====

``parent_id`` and ``host_id`` are extracted from the case's ``live_indices`` for
the ``parent`` and ``host`` identifiers respectively. The columns are always
present, even for case types that don't have such relationships.

Dynamic columns are added for each property in the data dictionary:

- Every property gets a raw text column: ``prop__<name>``
- ``date`` properties also get: ``prop__<name>__date`` (Date)
- ``number`` properties also get: ``prop__<name>__numeric`` (Numeric)


Schema evolution
----------------

Schema changes are **append-only**:

- New case property in the data dictionary → ``ALTER TABLE ADD COLUMN``
- Property removed from the data dictionary → column stops being
  populated but is never dropped
- New case type → new table

No columns are ever dropped and no tables are ever rebuilt. This means
schema evolution is always a trivial, non-blocking operation.


Population
----------

Cases are upserted via PostgreSQL's ``INSERT ... ON CONFLICT DO
UPDATE`` on ``case_id``. Type coercion for typed columns happens at
write time.

``send_to_project_db(case)``
    High-level function that accepts a ``CommCareCase``, resolves the
    table by reflection, and upserts. Raises ``LookupError`` if no
    table exists.


Management commands
-------------------

``populate_project_db <domain> [--all | --case-types x,y] [--since DATE]``
    Create/evolve tables and populate from live case data. First ensures the
    table schema is up-to-date, then iterates over cases to populate the tables

``drop_project_db_tables <domain>``
    Drop the entire schema for a domain (``DROP SCHEMA ... CASCADE``).
    Requires interactive confirmation.

``describe_project_db <domain>``
    Output DDL for a domain's tables using SQLAlchemy's
    ``CreateTable``/``CreateIndex`` compilers. Useful for feeding to an
    LLM to construct queries.

``query_project_db <domain> <sql>``
    Execute a SQL query with ``search_path`` scoped to the domain's
    schema. Provides a CSV dump of the results.


Key modules
-----------

``schema.py``
    Schema definition and DDL management:

    - ``get_schema_name(domain)`` — PostgreSQL schema name
    - ``build_all_table_schemas(domain)`` — build Tables for all case
      types from the data dictionary
    - ``sync_domain_tables(engine, domain)`` — create schema, create
      tables, evolve existing tables
    - ``get_case_table_schema(domain, case_type)`` — reflect a Table
      from the live database
    - ``create_tables(engine, metadata)`` — DDL creation
    - ``evolve_table(engine, table)`` — append-only schema evolution

``populate.py``
    Case data transformation and upsert:

    - ``send_to_project_db(case)`` — high-level single-case upsert
    - ``case_to_row_dict(case)`` — convert ``CommCareCase`` to a data
      dict with ``prop.`` namespaced keys

The public interface is defined in ``__init__.py``. Other modules should
interact with this one through that interface.
