Case Search Endpoints
=====================

A feature for building and managing configurable case search query endpoints
per domain. Each endpoint defines a structured filter query, a target case
type, and a set of named parameters that the query can reference.

As of now this is targeting the project database (in the ``project_db`` app).
If that does not pan out we might switch to ES.

Files
-----

Backend
~~~~~~~

- ``models.py`` — ``CaseSearchEndpoint`` and ``CaseSearchEndpointVersion`` models
- ``endpoint_capability.py`` — derives the capability document (available case
  types, fields, operations, auto-values) from the data dictionary
- ``endpoint_service.py`` — service layer: all reads/writes go through here
- ``endpoint_views.py`` — Django views wired to the service layer
- ``urls.py`` — URL routes for endpoint views

Frontend
~~~~~~~~

- ``static/case_search/js/endpoint_edit.js`` — Alpine.js query builder
- ``templates/case_search/endpoint_list.html`` — list view
- ``templates/case_search/endpoint_edit.html`` — create/edit/readonly view
- ``templates/case_search/partials/query_builder.html`` — query builder partial

Tests
~~~~~

- ``tests/test_endpoint_capability.py`` — unit tests for capability document logic
- ``tests/test_endpoint_service.py`` — unit tests for service layer functions

Architecture
------------

Service Layer
~~~~~~~~~~~~~

All business logic goes through ``endpoint_service.py``. Views call service
functions; they do not query models directly. This keeps the view layer thin
and makes it straightforward to add API views later (e.g. a REST API endpoint
that reuses the same service functions without duplicating logic).

Capability Document
~~~~~~~~~~~~~~~~~~~

``get_capability(domain)`` builds a JSON-serialisable dict describing what
queries are possible for a domain — derived from the data dictionary. It
includes:

- ``case_types`` — list of case types with their fields, field types, and
  valid operations per field
- ``auto_values`` — built-in dynamic value references (e.g. ``today()``)
- ``component_input_schemas`` — input slot definitions per operation

This document is passed to the frontend query builder and is also used
server-side by ``validate_filter_spec`` to validate saved queries.

Feature Flag
------------

This feature is gated behind the ``CASE_SEARCH_ENDPOINTS`` static toggle
(``TAG_INTERNAL``, domain-scoped). All endpoint views require it via
``toggles.CASE_SEARCH_ENDPOINTS.required_decorator()``.

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

- [x] No in-file styling — CSS for the query builder UI is not yet extracted into
      a proper stylesheet.
- [ ] Query tester — there is no way yet to run a query against real data from the
      edit view to verify results before saving.
- [ ] Better handling when the project data dictionary table is not present — the
      capability document currently assumes the data dictionary exists; domains
      without one get empty results with no clear feedback.
- [ ] Add ``require_can_edit_data`` to ``_ENDPOINT_DECORATORS`` and the tab entry
      in ``tabclasses.py`` — currently any domain member with the toggle can
      create/edit/delete endpoints.
- [ ] Fix race condition in ``save_new_version`` — concurrent saves read the same
      ``max_version`` and both try to insert ``max_version + 1``, causing an
      unhandled ``IntegrityError``. Use ``select_for_update()`` on the versions
      aggregate query.
- [ ] Handle ``IntegrityError`` from duplicate ``(domain, name)`` in
      ``create_endpoint`` — concurrent creates with the same name produce a 500;
      should return a 400 with a user-facing error.
- [ ] Add server-side validation of ``name`` and ``target_name`` in
      ``create_endpoint`` — empty strings pass through unvalidated.
- [ ] Add type guard in ``_validate_node`` — non-dict nodes in the query JSON
      (crafted POST) cause an ``AttributeError`` 500.
- [ ] Guard against missing ``name`` key in parameter objects in
      ``validate_filter_spec`` — currently raises ``KeyError``.
- [ ] Add recursion depth limit to ``_validate_node`` to prevent
      ``RecursionError`` on deeply nested queries.
- [ ] Guard against ``current_version = None`` in
      ``CaseSearchEndpointEditView.page_context`` — the field is nullable but the
      view assumes it is set.
- [ ] Fix ``CaseSearchCapabilityView`` — missing ``page_title``, unnecessarily
      inherits ``CaseSearchEndpointMixin``.
- [ ] Move inline ``onclick`` fetch in ``endpoint_list.html`` to a JS file.
- [ ] Add tests for unauthorized access (non-admin, wrong domain, no toggle).
