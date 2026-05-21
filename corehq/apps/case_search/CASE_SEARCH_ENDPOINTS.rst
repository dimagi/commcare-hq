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
- ``endpoint_views.py`` — Django views wired to the models
- ``urls.py`` — URL routes for endpoint views

Frontend
~~~~~~~~

- ``templates/case_search/endpoint_list.html`` — list view
- ``templates/case_search/endpoint_edit.html`` — create/edit view

Tests
~~~~~

- ``corehq/apps/case_search/tests/test_endpoint_views.py`` — unit tests for views

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

- [ ] Query Builder UI
- [ ] Query tester
- [ ] Add cards to layout
