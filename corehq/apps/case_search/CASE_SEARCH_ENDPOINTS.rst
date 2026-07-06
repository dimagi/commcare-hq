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
  parameter spec (``Parameter``, ``ParameterInput``), and validation logic
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

Endpoints can declare named, typed parameters (``text``, ``number``, ``date``,
``geopoint``). Parameters are stored as a JSON array on the
``CaseSearchEndpointVersion`` and validated against ``FIELD_TYPES`` from
``endpoint_capability``.

In the query spec, condition inputs can reference a parameter by name via a
``ParameterInput`` node (``{"type": "parameter", "value": "param_name"}``).
At query execution time, ``CaseSearchEndpointQueryBuilder`` resolves each
``ParameterInput`` against the supplied criteria values before building the ES
filter.

Query Builder
-------------

The query builder UI (``endpoint_edit.html`` + ``endpoint_edit.js``) renders
a tree of group and condition nodes backed by a JSON query spec. Adding a
condition row triggers an HTMX fetch to ``condition_row.html``, which renders
the appropriate operator/input controls for the selected field type. Condition
inputs can be set to a literal value or bound to a declared parameter.

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
- [ ] Guard with role permission (right now everybody on domain can see the views)
- [ ] Allow usage of today's date, user id, etc.
  - Either an option in the endpoint config
  - Or via separately configured parameters on the case list page
- [ ] Paginate endpoint list view (currently unbounded query)
