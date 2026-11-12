Case Search Endpoints
=====================

A feature for building and managing configurable case search query endpoints
per domain. Each endpoint defines a structured filter query, a target case
type, and a set of named parameters that the query can reference.

Initially we were targeting ES. But SQL turned out to be the better option.
There is still ES related code around that is not reachable by the user.
Once we decide that we will not re-prioritize ES, we will remove that code.

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
(``text``, ``number``, ``date``, ``geopoint``) plus two parameter-only types
that no field has, so they have no operations and cannot be referenced from
an Elasticsearch query spec: ``daterange``, and ``select``, since a multiple
choice case property is plain text to case search.

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
SQL into SQLAlchemy Core. ``_rows_to_fixture`` renders the rows directly as
the results fixture, without loading cases.

Saving checks that the SQL can be translated and that its placeholders match
the declared parameters (``validate_parameters_match_placeholders``).
Anything else fails when the query runs, and query authors are expected to
try it in the query tester.



Query Tester
------------

The query tester partial (``query_tester.html``) renders one input per
declared parameter and POSTs the query and the raw input values to
``CaseSearchEndpointTestView``.

Versioning
----------

Each ``CaseSearchEndpoint`` keeps a full history of ``CaseSearchEndpointVersion``
records. A mobile app can reference a specific version number to get a stable,
unchanging query definition — saves that have already been deployed are never
mutated. Saving changes always creates a new version; ``current_version``
points to the latest. Whether this versioning scheme stays long-term is still
an open question. The only exception is deletions of endpoints. The who and when
is stored on the endpoint itself, which was requried to maked linked projects work.

TODOs
-----

- [ ] Sort configuration
- [ ] Paginate endpoint list view (currently unbounded query)
