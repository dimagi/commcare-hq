Case Search Endpoints
=====================

A feature for building and managing configurable case search query endpoints
per domain. Each endpoint defines a structured filter query, a target case
type, and a set of named parameters that the query can reference.

Initially we will target ES with the query but might switch to the project DB
if it proves beneficial.

Files
-----

Backend
~~~~~~~

- ``models.py`` — ``CaseSearchEndpoint`` and ``CaseSearchEndpointVersion`` models
- ``endpoint_capability.py`` — domain capability metadata (case types, fields,
  operators, input schemas); drives both UI and query validation
- ``endpoint_query_spec.py`` — query AST (``GroupNode``, ``ComponentNode``),
  parameter spec (``Parameter``, ``ParameterInput``), validation logic, and
  the SQL parameter binding (``sql_placeholders``, ``bind_values``)
- ``endpoint_views.py`` — Django views wired to the models
- ``utils.py`` — ``CaseSearchEndpointQueryBuilder``: compiles the validated
  AST and parameter values into an ES query

Frontend
~~~~~~~~

- ``templates/case_search/endpoint_list.html`` — list view
- ``templates/case_search/endpoint_edit.html`` — create/edit view with query
  builder and parameter configuration UI
- ``templates/case_search/partials/condition_row.html`` — query builder
  condition row partial (HTMX-swapped)
- ``templates/case_search/partials/query_tester.html`` — inline query tester
  with parameter value inputs
- ``static/case_search/js/endpoint_edit.js`` — Alpine.js component driving the
  query builder and parameter UI

Tests
~~~~~

- ``tests/test_endpoint_capability.py`` — capability metadata generation
- ``tests/test_endpoint_query_spec.py`` — query spec parsing and validation,
  including parameter spec and parameter input resolution
- ``tests/test_endpoint_views.py`` — view-level tests (create, edit, deactivate,
  query tester)
- ``tests/test_utils.py`` — ``CaseSearchEndpointQueryBuilder`` operator dispatch,
  including geopoint ``within_distance``

Feature Flag
------------

This feature is gated behind the ``CASE_SEARCH_ENDPOINTS`` static toggle
(``TAG_INTERNAL``, domain-scoped). All endpoint views require it via
``toggles.CASE_SEARCH_ENDPOINTS.required_decorator()``.

Parameters
----------

Endpoints of both kinds declare named, typed parameters, stored as a JSON
array on the ``CaseSearchEndpointVersion`` and validated against
``PARAMETER_TYPES`` from ``endpoint_capability``. That is the field types
(``text``, ``number``, ``date``, ``select``, ``geopoint``) plus ``daterange``,
which is parameter-only: no case property has that type, so it has no
operations and cannot be referenced from an Elasticsearch query spec.

In the query spec, condition inputs can reference a parameter by name via a
``ParameterInput`` node (``{"type": "parameter", "value": "param_name"}``).
At query execution time, ``CaseSearchEndpointQueryBuilder`` resolves each
``ParameterInput`` against the supplied criteria values before building the ES
filter.

Project DB endpoints bind parameters into their SQL instead.
``sql_placeholders`` gives the placeholder names a spec implies — a
``daterange`` named ``dob`` becomes ``:dob_from`` and ``:dob_to``, every other
type keeps its own name — and ``bind_values`` maps a request's search criteria
onto the values those placeholders take:

- An absent or blank criterion binds as ``None``. NULL coerces to any column
  type, so endpoint SQL guards each parameter with ``(:p IS NULL OR ...)``;
  an empty string would fail against a numeric or date column.
- A ``select`` parameter always binds as a list, however many values were
  searched for, so that the SQL comparing it against an array column works
  whatever the searcher chose.
- Multiple values for a scalar parameter are a ``CaseSearchUserError``.

Query Builder
-------------

The query builder UI (``endpoint_edit.html`` + ``endpoint_edit.js``) renders
a tree of group and condition nodes backed by a JSON query spec. Adding a
condition row triggers an HTMX fetch to ``condition_row.html``, which renders
the appropriate operator/input controls for the selected field type. Condition
inputs can be set to a literal value or bound to a declared parameter.

Project DB Endpoints
--------------------

An endpoint's ``target_type`` selects its backend. A ``project_db`` endpoint
stores SQL in ``dangerous_sql`` instead of a query spec, and runs it through
``corehq.apps.project_db.user_sql``, which translates a restricted subset of
SQL into SQLAlchemy Core. Rows are mapped back to ``CommCareCase`` objects by
``_rows_to_cases``, so both kinds of endpoint return the same thing.

The SQL is validated when the endpoint is saved (``sql_parameter_errors``),
which reports at save time what would otherwise fail at run time:

- a placeholder the parameter spec does not declare, or a declared parameter
  the SQL never uses — ``UserSQL.run`` rejects a mismatched value set
- a parameter used with ``IN``, whose unsupplied form renders nothing at all
  and raises out of psycopg2
- a ``select`` parameter not compared against a ``select_prop__`` array
  column, or a scalar parameter that is

List comparisons therefore go through the ``select_prop__`` columns, using
``&&`` (any of) or ``@>`` (all of). Multi-value search over a plain text
property is deliberately not expressible.

Query Tester
------------

The query tester partial (``query_tester.html``) renders one input per
declared parameter and POSTs the query + parameter values to
``CaseSearchEndpointTestView``. Results are swapped in via HTMX. The test
view validates the case type and query spec before executing; unknown case
types and malformed queries return user-readable errors rather than 500s.

Versioning
----------

Each ``CaseSearchEndpoint`` keeps a full history of ``CaseSearchEndpointVersion``
records. A mobile app can reference a specific version number to get a stable,
unchanging query definition — saves that have already been deployed are never
mutated. Saving changes always creates a new version; ``current_version``
points to the latest. Whether this versioning scheme stays long-term is still
an open question.

TODOs
-----

- [ ] Sort configuration
- [ ] Paginate endpoint list view (currently unbounded query)
