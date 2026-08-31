# CommCare API OpenAPI Specs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate OpenAPI 3.0.3 specifications for the CommCare data APIs from
the API code itself, and make those specs the source of truth for the published
API documentation.

**Architecture:** A new `corehq/apps/api/openapi/` package holds a catalogue of
routed API resources (which `urls.py` also consumes, so routing and
documentation cannot diverge), adapters that turn Tastypie's existing
`build_schema()` output and hand-written in-code documentation into OpenAPI
operations, and a management command that writes committed spec artifacts. The
published reStructuredText pages become thin `openapi::` directives rendered by
`sphinxcontrib-openapi`.

**Tech Stack:** Python, Django, django-tastypie 0.15.1, jsonobject, pytest,
Sphinx with `sphinxcontrib-openapi`, `openapi-spec-validator`, `openapi-core`.

**Spec:** `docs/superpowers/specs/2026-08-17-commcare-api-openapi-design.md`

## Global Constraints

- OpenAPI version emitted is exactly **3.0.3**. Do not emit 3.1 — the renderer's
  support is unconfirmed (see Task 10).
- Target Tastypie version is **django-tastypie 0.15.1**.
- Ruff config for this repo: `line-length = 79` for formatting,
  `max-line-length = 115` for pycodestyle, `quote-style = 'single'`. Run
  `uv run ruff format <paths>` and `uv run ruff check <paths>` before each
  commit.
- `DJANGO_SETTINGS_MODULE` for tests is `testsettings` (configured in
  `pyproject.toml`); pytest collects any file under a `tests/` directory
  (`python_files` includes `*/tests/*.py`).
- Test command: `uv run pytest --reusedb=1 <path>`. If `uv run` fails in your
  environment with a dependency resolution error, `.venv/bin/pytest` works
  against the existing virtualenv.
- Legacy `v0.3`–`v0.6` URLs registered through `versioned_apis()` /
  `_OLD_API_LIST` are **out of scope** and must not be modified.
- Admin and accounting resources are **not** publicly documented.
- Every generated spec must pass `openapi-spec-validator`.

## Design points the tasks depend on

All of these are specified in the design doc; they are listed here because a
task's code will look wrong if you have not read them.

1. **The catalogue covers only `get_urlpattern`-routed resources** — the
   domain-scoped and user-scoped ones. `ADMIN_API_LIST` registers through
   `CommCareHqApi(api_name='global')` instead and stays exactly as it is.
2. **`doc_slug` names the generated spec document, not a documentation page.**
   Pages are not one-to-one with resources, so several pages may render from one
   spec, filtered with the directive's `:paths:` / `:include:` option.
3. **Item schemas for untyped containers live in `Docs.field_schemas`**, merged
   over whatever the field introspects to. There is no `schema=` field argument.
4. **`Docs` is collected by walking the MRO** and reading
   `klass.__dict__['Docs']` per class — never `resource_cls.Docs`, which would
   hide a parent's declaration behind a subclass's own.
5. **Write operations carry a `requestBody`** built from the writable fields
   only. `POST` on a list path and `PUT`/`PATCH` on a detail path get one; `GET`
   and `DELETE` do not.

## File structure

Created:

| File                                                              | Responsibility                                                                       |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `corehq/apps/api/openapi/__init__.py`                             | Package marker                                                                       |
| `corehq/apps/api/openapi/catalogue.py`                            | `ApiEntry` and the ordered `CATALOGUE`; consumed by both `urls.py` and the generator |
| `corehq/apps/api/openapi/docs.py`                                 | Collects in-code documentation: `Docs` MRO merge, generic-`help_text` detection      |
| `corehq/apps/api/openapi/schema.py`                               | `build_schema()` field info → JSON Schema                                            |
| `corehq/apps/api/openapi/operations.py`                           | Resource → OpenAPI paths, operations, parameters                                     |
| `corehq/apps/api/openapi/security.py`                             | `securitySchemes` and required-permission text                                       |
| `corehq/apps/api/openapi/builder.py`                              | Assembles whole OpenAPI documents                                                    |
| `corehq/apps/api/openapi/view_adapter.py`                         | `@api_docs` decorator for function-based views                                       |
| `corehq/apps/api/openapi/jsonobject_schema.py`                    | `jsonobject` class → JSON Schema                                                     |
| `corehq/apps/api/openapi/examples/`                               | JSON example payloads referenced from `Docs`                                         |
| `corehq/apps/api/openapi/management/commands/generate_openapi.py` | Writes the artifacts                                                                 |
| `corehq/apps/api/openapi/tests/`                                  | Unit tests for the above                                                             |
| `corehq/apps/api/tests/test_urls.py`                              | URL-pattern regression guard for the `urls.py` refactor                              |
| `docs/api/spec/`                                                  | Committed generated specs (one per `doc_slug`, plus `bundle.json`)                   |

Modified: `corehq/apps/api/urls.py` (routes from the catalogue),
`corehq/apps/api/resources/*.py` and other resource modules (add `help_text` and
`Docs`), `docs/conf.py` (Sphinx extension), `docs/api/*.rst` (become
directives), `pyproject.toml` (dependencies).

---

### Task 1: URL pattern regression guard

The next task refactors `urls.py`. Django resolves URLs in order, so this guard
locks the current patterns and their order first. This is a regression test, not
a TDD red test — it passes immediately and must keep passing.

**Files:**

- Create: `corehq/apps/api/tests/test_urls.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `EXPECTED_DOMAIN_PATTERNS`, `EXPECTED_USER_PATTERNS` — module-level
  lists later tasks must not edit when refactoring.

- [ ] **Step 1: Write the guard test**

The pattern strings below were captured from the current `urls.py`. Copy them
verbatim — they are the assertion.

```python
from corehq.apps.api import urls as api_urls

# Snapshot of corehq.apps.api.urls.urlpatterns, in resolution order.
# Django matches URLs in order, so both membership and order matter.
EXPECTED_DOMAIN_PATTERNS = [
    '(?P<api_version>v0.5)/odata/cases/',
    '(?P<api_version>v0.5)/odata/forms/',
    'odata/cases/(?P<api_version>v1)/',
    'odata/forms/(?P<api_version>v1)/',
    '(?P<api_version>v0.5)/messaging-event/$',
    '(?P<api_version>v0.5)/messaging-event/(?P<event_id>\\d+)/$',
    'messaging-event/(?P<api_version>v1)/$',
    'messaging-event/(?P<api_version>v1)/(?P<event_id>\\d+)/$',
    'v0\\.6/case/bulk-fetch/$',
    'v0.6/case/?$',
    'v0\\.6/case/(?P<case_id>[\\w\\-,]+)/?$',
    'v0.6/case/ext/<path:external_id>/',
    'case/v2/bulk-fetch/$',
    'case/v2/?$',
    'case/v2/(?P<case_id>[\\w\\-,]+)/?$',
    'case/v2/ext/<path:external_id>/',
    '',
    '^case/attachment/(?P<case_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    '^case_attachment/v1/(?P<case_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    '^form/attachment/(?P<instance_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    '^form_attachment/v1/(?P<instance_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    'case/custom/<slug:api_id>/',
    '(?P<api_version>v0.5)/ucr/',
    'ucr/(?P<api_version>v1)/',
    '^(?P<resource_name>application)/(?P<api_name>v1)/',
    '^(?P<resource_name>case)/(?P<api_name>v1)/',
    '^(?P<resource_name>form)/(?P<api_name>v1)/',
    '^(?P<resource_name>sso)/(?P<api_name>v1)/',
    '^(?P<resource_name>user)/(?P<api_name>v1)/',
    '^(?P<resource_name>web-user)/(?P<api_name>v1)/',
    '^(?P<resource_name>group)/(?P<api_name>v1)/',
    '^(?P<resource_name>bulk-user)/(?P<api_name>v1)/',
    '^(?P<resource_name>fixture_internal)/(?P<api_name>v1)/',
    '^(?P<resource_name>fixture)/(?P<api_name>v1)/',
    '^(?P<resource_name>device-log)/(?P<api_name>v1)/',
    '^(?P<resource_name>project_space_metadata)/(?P<api_name>v1)/',
    '^(?P<resource_name>location)/(?P<api_name>v1)/',
    '^(?P<resource_name>location)/(?P<api_name>v2)/',
    '^(?P<resource_name>location_type)/(?P<api_name>v1)/',
    '^(?P<resource_name>simplereportconfiguration)/(?P<api_name>v1)/',
    '^(?P<resource_name>configurablereportdata)/(?P<api_name>v1)/',
    '^(?P<resource_name>ucr_data_source)/(?P<api_name>v1)/',
    '^(?P<resource_name>domain_forms)/(?P<api_name>v1)/',
    '^(?P<resource_name>domain_cases)/(?P<api_name>v1)/',
    '^(?P<resource_name>domain_usernames)/(?P<api_name>v1)/',
    '^(?P<resource_name>location_internal)/(?P<api_name>v1)/',
    '^(?P<resource_name>odata/cases)/(?P<api_name>v1)/',
    '^(?P<resource_name>odata/forms)/(?P<api_name>v1)/',
    '^(?P<resource_name>lookup_table)/(?P<api_name>v1)/',
    '^(?P<resource_name>lookup_table_item)/(?P<api_name>v1)/',
    '^(?P<resource_name>lookup_table_item)/(?P<api_name>v2)/',
    '^(?P<resource_name>action_times)/(?P<api_name>v1)/',
    '^(?P<resource_name>analytics-roles)/(?P<api_name>v1)/',
    '^(?P<resource_name>invitation)/(?P<api_name>v1)/',
    '^(?P<resource_name>det_export_instance)/(?P<api_name>v1)/',
]

EXPECTED_USER_PATTERNS = [
    '',
    '^(?P<resource_name>identity)/(?P<api_name>v1)/',
    '^(?P<resource_name>user_domains)/(?P<api_name>v1)/',
]


def test_domain_url_patterns_and_order_unchanged():
    actual = [str(p.pattern) for p in api_urls.urlpatterns]
    assert actual == EXPECTED_DOMAIN_PATTERNS


def test_user_url_patterns_and_order_unchanged():
    actual = [str(p.pattern) for p in api_urls.user_urlpatterns]
    assert actual == EXPECTED_USER_PATTERNS
```

- [ ] **Step 2: Run the test to verify it passes against current code**

Run: `uv run pytest --reusedb=1 corehq/apps/api/tests/test_urls.py -v` Expected:
2 passed. If it fails, the snapshot above is stale — regenerate it by printing
`[str(p.pattern) for p in api_urls.urlpatterns]` and update the lists, noting
the difference in your commit message.

- [ ] **Step 3: Lint and commit**

```bash
uv run ruff format corehq/apps/api/tests/test_urls.py
uv run ruff check corehq/apps/api/tests/test_urls.py
git add corehq/apps/api/tests/test_urls.py
git commit -m "Add URL pattern regression guard for the API app"
```

---

### Task 2: API catalogue, and route from it

**Files:**

- Create: `corehq/apps/api/openapi/__init__.py`
- Create: `corehq/apps/api/openapi/catalogue.py`
- Create: `corehq/apps/api/openapi/tests/__init__.py`
- Create: `corehq/apps/api/openapi/tests/test_catalogue.py`
- Modify: `corehq/apps/api/urls.py`

**Interfaces:**

- Consumes: `EXPECTED_DOMAIN_PATTERNS` / `EXPECTED_USER_PATTERNS` from Task 1
  (must stay green).
- Produces:

  - `ApiEntry(resource: type, version: str, doc_slug: str | None = None, scope: str = 'domain')`
    — frozen dataclass.
  - `CATALOGUE: tuple[ApiEntry, ...]` — ordered to match current routing.
  - `entries_for_scope(scope: str) -> list[ApiEntry]`
  - `documented_entries() -> list[ApiEntry]` — entries whose `doc_slug` is set.

- [ ] **Step 1: Write the failing test**

```python
from corehq.apps.api.openapi.catalogue import (
    CATALOGUE,
    documented_entries,
    entries_for_scope,
)


def test_every_entry_has_a_known_scope():
    assert {e.scope for e in CATALOGUE} <= {'domain', 'user'}


def test_domain_entries_are_in_routing_order():
    names = [
        (e.resource(api_name=e.version)._meta.resource_name, e.version)
        for e in entries_for_scope('domain')
    ]
    assert names[:4] == [
        ('application', 'v1'),
        ('case', 'v1'),
        ('form', 'v1'),
        ('sso', 'v1'),
    ]
    assert ('location', 'v2') in names
    assert ('det_export_instance', 'v1') in names


def test_documented_entries_are_a_subset_with_unique_slugs():
    documented = documented_entries()
    assert documented, 'expected at least one documented entry'
    assert set(documented) <= set(CATALOGUE)
    slugs = [e.doc_slug for e in documented]
    assert len(slugs) == len(set(slugs))


def test_user_scoped_entries():
    names = [
        (e.resource(api_name=e.version)._meta.resource_name, e.version)
        for e in entries_for_scope('user')
    ]
    assert names == [('identity', 'v1'), ('user_domains', 'v1')]


def test_every_catalogued_resource_can_build_a_schema():
    """The generator depends on this for every resource in the catalogue.

    Note this is ``build_schema()`` called in-process. Tastypie's own
    ``.../schema/`` HTTP endpoint is separately broken for resources that
    are not ``ModelResource`` subclasses; see the design doc.
    """
    failures = {}
    for entry in CATALOGUE:
        resource = entry.resource(api_name=entry.version)
        try:
            schema = resource.build_schema()
        except Exception as exc:
            failures[entry.resource.__name__] = repr(exc)
            continue
        assert schema['fields'], entry.resource.__name__
    assert not failures
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_catalogue.py -v`
Expected: FAIL —
`ModuleNotFoundError: No module named 'corehq.apps.api.openapi'`

- [ ] **Step 3: Write the catalogue**

Create `corehq/apps/api/openapi/__init__.py` and
`corehq/apps/api/openapi/tests/__init__.py` as empty files, then `catalogue.py`.
The entry order is copied from the current `get_urlpattern` sequence in
`urls.py` — do not reorder it.

```python
"""The registry of routed CommCare API resources.

``corehq.apps.api.urls`` builds its URL patterns from this catalogue, and the
OpenAPI generator reads the same list. A resource therefore cannot be routed
without appearing here, and the generated specs cannot describe an endpoint
that is not routed.

Order matters: Django resolves URL patterns in order.
"""
from dataclasses import dataclass

from corehq.apps.api.domain_metadata import DomainMetadataResource
from corehq.apps.api.resources import v0_4, v0_5, v1_0
from corehq.apps.api.resources.v0_5 import (
    DomainCases,
    DomainForms,
    DomainUsernames,
    UserDomainsResource,
)
from corehq.apps.fixtures import resources as fixtures
from corehq.apps.locations import resources as locations

DOMAIN = 'domain'
USER = 'user'


@dataclass(frozen=True)
class ApiEntry:
    """One routed resource version.

    ``doc_slug`` is the basename of the generated spec document, or ``None``
    for resources that are routed but not publicly documented. Several
    documentation pages may render from one spec.
    """

    resource: type
    version: str
    doc_slug: str | None = None
    scope: str = DOMAIN


CATALOGUE = (
    ApiEntry(v0_4.ApplicationResource, 'v1', 'application-v1'),
    ApiEntry(v0_4.CommCareCaseResource, 'v1', 'case-v1'),
    ApiEntry(v0_4.XFormInstanceResource, 'v1', 'form-v1'),
    ApiEntry(v0_4.SingleSignOnResource, 'v1', 'sso-v1'),
    ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1'),
    ApiEntry(v0_5.WebUserResource, 'v1', 'web-user-v1'),
    ApiEntry(v0_5.GroupResource, 'v1', 'group-v1'),
    ApiEntry(v0_5.BulkUserResource, 'v1', 'bulk-user-v1'),
    ApiEntry(fixtures.v0_1.InternalFixtureResource, 'v1'),
    ApiEntry(fixtures.v0_1.FixtureResource, 'v1', 'fixture-v1'),
    ApiEntry(v0_5.DeviceReportResource, 'v1'),
    ApiEntry(DomainMetadataResource, 'v1'),
    ApiEntry(locations.v0_5.LocationResource, 'v1', 'location-v1'),
    ApiEntry(locations.v0_6.LocationResource, 'v2', 'location-v2'),
    ApiEntry(locations.v0_5.LocationTypeResource, 'v1', 'location-type-v1'),
    ApiEntry(
        v0_5.SimpleReportConfigurationResource, 'v1', 'report-config-v1'
    ),
    ApiEntry(v0_5.ConfigurableReportDataResource, 'v1', 'report-data-v1'),
    ApiEntry(v0_5.DataSourceConfigurationResource, 'v1'),
    ApiEntry(DomainForms, 'v1'),
    ApiEntry(DomainCases, 'v1'),
    ApiEntry(DomainUsernames, 'v1'),
    ApiEntry(locations.v0_1.InternalLocationResource, 'v1'),
    ApiEntry(v0_5.ODataCaseResource, 'v1'),
    ApiEntry(v0_5.ODataFormResource, 'v1'),
    ApiEntry(fixtures.v0_1.LookupTableResource, 'v1', 'lookup-table-v1'),
    ApiEntry(
        fixtures.v0_1.LookupTableItemResource, 'v1', 'lookup-table-item-v1'
    ),
    ApiEntry(
        fixtures.v0_6.LookupTableItemResource, 'v2', 'lookup-table-item-v2'
    ),
    ApiEntry(v0_5.NavigationEventAuditResource, 'v1'),
    ApiEntry(v1_0.CommCareAnalyticsUserResource, 'v1'),
    ApiEntry(v1_0.InvitationResource, 'v1'),
    ApiEntry(v1_0.DETExportInstanceResource, 'v1', 'det-export-v1'),
    ApiEntry(v0_5.IdentityResource, 'v1', scope=USER),
    ApiEntry(UserDomainsResource, 'v1', 'user-domains-v1', scope=USER),
)


def entries_for_scope(scope):
    return [entry for entry in CATALOGUE if entry.scope == scope]


def documented_entries():
    return [entry for entry in CATALOGUE if entry.doc_slug]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_catalogue.py -v`
Expected: 5 passed.

- [ ] **Step 5: Route from the catalogue**

In `corehq/apps/api/urls.py`, replace the flat run of `X.get_urlpattern('v1')`
lines at the end of `urlpatterns` with a comprehension over the catalogue, and
do the same in `user_urlpatterns`. Keep everything else — `_OLD_API_LIST`,
`versioned_apis()`, `ADMIN_API_LIST`, the non-Tastypie routes — untouched.

```python
from corehq.apps.api.openapi.catalogue import DOMAIN, USER, entries_for_scope

# ... existing non-Tastypie urlpatterns entries stay exactly as they are ...

urlpatterns = [
    # ... unchanged entries, through the ucr routes ...
    *[
        entry.resource.get_urlpattern(entry.version)
        for entry in entries_for_scope(DOMAIN)
    ],
]

user_urlpatterns = [
    path('', include(list(versioned_apis(VERSIONED_USER_API_LIST)))),
    *[
        entry.resource.get_urlpattern(entry.version)
        for entry in entries_for_scope(USER)
    ],
]
```

Then delete the now-unused resource imports that only the deleted lines
referenced — `ruff check` will report them as unused (F401). Imports still
needed by `_OLD_API_LIST` and `ADMIN_API_LIST` must stay.

- [ ] **Step 6: Run the guard and the catalogue tests together**

Run:

```bash
uv run pytest --reusedb=1 corehq/apps/api/tests/test_urls.py \
  corehq/apps/api/openapi/tests/test_catalogue.py -v
```

Expected: 6 passed. A failure here means the catalogue order does not match the
previous routing order — fix the catalogue, not the snapshot.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi corehq/apps/api/urls.py
uv run ruff check corehq/apps/api/openapi corehq/apps/api/urls.py
git add corehq/apps/api/openapi corehq/apps/api/urls.py
git commit -m "Route API resources from a catalogue

The catalogue is the single list of routed resource versions. The OpenAPI
generator reads the same list, so a documented endpoint cannot drift from a
routed one."
```

---

### Task 3: In-code documentation collection

**Files:**

- Create: `corehq/apps/api/openapi/docs.py`
- Create: `corehq/apps/api/openapi/tests/test_docs.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `collect_docs(resource_cls: type) -> dict` — merges `Docs` inner classes
    across the MRO; subclass values win; dict values are shallow-merged. Keys:
    `summary`, `description`, `permissions`, `examples`, `field_schemas`,
    `parameters`.
  - `GENERIC_HELP_TEXTS: frozenset[str]`
  - `field_description(help_text: str | None) -> str | None` — returns `None`
    for empty or generic class-default text.

Note: an inner class is inherited by normal attribute lookup, so
`resource_cls.Docs` would silently return a parent's `Docs` and lose the
subclass's own. `collect_docs` must read `klass.__dict__['Docs']` per class in
the MRO instead.

- [ ] **Step 1: Write the failing test**

```python
from corehq.apps.api.openapi.docs import (
    collect_docs,
    field_description,
    GENERIC_HELP_TEXTS,
)


class Base:
    class Docs:
        summary = 'Base summary'
        description = 'Base description'
        examples = {'list': 'base/list.json'}
        field_schemas = {'a': {'type': 'string'}}


class Child(Base):
    class Docs:
        summary = 'Child summary'
        examples = {'detail': 'child/detail.json'}
        field_schemas = {'b': {'type': 'integer'}}


class Grandchild(Child):
    pass


def test_subclass_overrides_scalar_and_merges_dicts():
    docs = collect_docs(Child)
    assert docs['summary'] == 'Child summary'
    assert docs['description'] == 'Base description'
    assert docs['examples'] == {
        'list': 'base/list.json',
        'detail': 'child/detail.json',
    }
    assert docs['field_schemas'] == {
        'a': {'type': 'string'},
        'b': {'type': 'integer'},
    }


def test_class_without_its_own_docs_inherits_the_merge():
    assert collect_docs(Grandchild) == collect_docs(Child)


def test_class_with_no_docs_anywhere():
    class Bare:
        pass

    assert collect_docs(Bare) == {}


def test_tastypie_and_hq_class_defaults_are_generic():
    assert 'Unicode string data. Ex: "Hello World"' in GENERIC_HELP_TEXTS
    assert 'A UUID object' in GENERIC_HELP_TEXTS


def test_field_description_rejects_generic_and_empty_text():
    assert field_description(None) is None
    assert field_description('') is None
    assert field_description('Integer data. Ex: 2673') is None
    assert field_description('A UUID object') is None
    assert field_description('The user\'s login name.') == (
        "The user's login name."
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_docs.py -v`
Expected: FAIL —
`ModuleNotFoundError: No module named 'corehq.apps.api.openapi.docs'`

- [ ] **Step 3: Write the implementation**

```python
"""Collection of hand-written API documentation held in the code.

Field descriptions use Tastypie's ``help_text``. Endpoint-level narrative
lives in a ``Docs`` inner class on the resource, which is merged across the
class hierarchy so that a subclass inherits its parent's documentation and
overrides only what it changes.
"""
from tastypie.fields import ApiField

DOCS_KEYS = (
    'summary',
    'description',
    'permissions',
    'examples',
    'field_schemas',
    'parameters',
)


def _generic_help_texts():
    """Every ``help_text`` that is a field class default, not a description."""
    from corehq.apps.api import fields as hq_fields
    from tastypie import fields as tastypie_fields

    texts = set()
    for module in (tastypie_fields, hq_fields):
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, ApiField):
                texts.add(value.help_text)
    return frozenset(texts)


GENERIC_HELP_TEXTS = _generic_help_texts()


def collect_docs(resource_cls):
    """Merge ``Docs`` inner classes across ``resource_cls``'s MRO.

    Subclasses win over base classes. Dict values are shallow-merged so that,
    for example, a subclass can add one example without restating the others.
    """
    merged = {}
    for klass in reversed(resource_cls.__mro__):
        docs = klass.__dict__.get('Docs')
        if docs is None:
            continue
        for key in DOCS_KEYS:
            value = docs.__dict__.get(key)
            if value is None:
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def field_description(help_text):
    """The field's description, or ``None`` if it is undocumented."""
    if not help_text or help_text in GENERIC_HELP_TEXTS:
        return None
    return help_text
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_docs.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi
uv run ruff check corehq/apps/api/openapi
git add corehq/apps/api/openapi
git commit -m "Add in-code API documentation collection"
```

---

### Task 4: Field schema mapping

**Files:**

- Create: `corehq/apps/api/openapi/schema.py`
- Create: `corehq/apps/api/openapi/tests/test_schema.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `TYPE_MAP: dict[str, dict]` — Tastypie `dehydrated_type` → JSON Schema
    fragment.
  - `field_to_schema(field_info: dict, *, override: dict | None = None) -> dict`
    where `field_info` is one value from `build_schema()['fields']`.

`field_info` keys used: `type`, `nullable`, `readonly`, `default`, `help_text`.
Note OpenAPI 3.0.3 spells nullability `nullable: true`, not a type array.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from tastypie.fields import NOT_PROVIDED

from corehq.apps.api.openapi.schema import TYPE_MAP, field_to_schema


def field_info(**overrides):
    info = {
        'type': 'string',
        'nullable': False,
        'blank': False,
        'readonly': False,
        'unique': False,
        'primary_key': False,
        'default': NOT_PROVIDED,
        'help_text': 'Unicode string data. Ex: "Hello World"',
        'verbose_name': 'thing',
    }
    info.update(overrides)
    return info


@pytest.mark.parametrize('dehydrated_type, expected', [
    ('string', {'type': 'string'}),
    ('integer', {'type': 'integer'}),
    ('float', {'type': 'number'}),
    ('decimal', {'type': 'string', 'format': 'decimal'}),
    ('boolean', {'type': 'boolean'}),
    ('list', {'type': 'array', 'items': {}}),
    ('dict', {'type': 'object', 'additionalProperties': True}),
    ('date', {'type': 'string', 'format': 'date'}),
    ('datetime', {'type': 'string', 'format': 'date-time'}),
    ('time', {'type': 'string', 'format': 'time'}),
    ('related', {'type': 'string', 'format': 'uri'}),
])
def test_every_dehydrated_type_maps(dehydrated_type, expected):
    assert field_to_schema(field_info(type=dehydrated_type)) == expected


def test_unknown_type_falls_back_to_permissive_schema():
    assert field_to_schema(field_info(type='mystery')) == {}


def test_nullable_uses_openapi_30_spelling():
    schema = field_to_schema(field_info(nullable=True))
    assert schema == {'type': 'string', 'nullable': True}


def test_readonly_field():
    schema = field_to_schema(field_info(readonly=True))
    assert schema == {'type': 'string', 'readOnly': True}


def test_documented_help_text_becomes_the_description():
    schema = field_to_schema(field_info(help_text='The primary phone number.'))
    assert schema['description'] == 'The primary phone number.'


def test_generic_help_text_produces_no_description():
    assert 'description' not in field_to_schema(field_info())


def test_not_provided_default_is_omitted():
    assert 'default' not in field_to_schema(field_info())


def test_concrete_default_is_included():
    schema = field_to_schema(field_info(type='boolean', default=False))
    assert schema['default'] is False


def test_callable_default_is_omitted():
    schema = field_to_schema(field_info(default=lambda: 'x'))
    assert 'default' not in schema


def test_override_replaces_generated_keys():
    schema = field_to_schema(
        field_info(type='list'),
        override={'items': {'type': 'string'}},
    )
    assert schema == {'type': 'array', 'items': {'type': 'string'}}


def test_type_map_covers_all_tastypie_types():
    from tastypie import fields as tastypie_fields

    declared = {
        value.dehydrated_type
        for value in vars(tastypie_fields).values()
        if isinstance(value, type)
        and issubclass(value, tastypie_fields.ApiField)
    }
    assert declared <= set(TYPE_MAP)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_schema.py -v`
Expected: FAIL —
`ModuleNotFoundError: No module named 'corehq.apps.api.openapi.schema'`

- [ ] **Step 3: Write the implementation**

```python
"""Mapping from Tastypie field metadata to OpenAPI 3.0.3 schema objects."""
from tastypie.fields import NOT_PROVIDED

from corehq.apps.api.openapi.docs import field_description

TYPE_MAP = {
    'string': {'type': 'string'},
    'integer': {'type': 'integer'},
    'float': {'type': 'number'},
    'decimal': {'type': 'string', 'format': 'decimal'},
    'boolean': {'type': 'boolean'},
    'list': {'type': 'array', 'items': {}},
    'dict': {'type': 'object', 'additionalProperties': True},
    'date': {'type': 'string', 'format': 'date'},
    'datetime': {'type': 'string', 'format': 'date-time'},
    'time': {'type': 'string', 'format': 'time'},
    'related': {'type': 'string', 'format': 'uri'},
}


def field_to_schema(field_info, *, override=None):
    """Convert one ``build_schema()`` field entry to a schema object.

    ``override`` is merged last, so a hand-written ``Docs.field_schemas``
    entry wins over anything derived from the field.
    """
    schema = dict(TYPE_MAP.get(field_info['type'], {}))

    description = field_description(field_info.get('help_text'))
    if description:
        schema['description'] = description

    if field_info.get('nullable'):
        schema['nullable'] = True
    if field_info.get('readonly'):
        schema['readOnly'] = True

    default = field_info.get('default')
    if default is not NOT_PROVIDED and not callable(default):
        schema['default'] = default

    if override:
        schema.update(override)
    return schema
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_schema.py -v`
Expected: 22 passed.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi
uv run ruff check corehq/apps/api/openapi
git add corehq/apps/api/openapi
git commit -m "Map Tastypie field types to OpenAPI schemas"
```

---

### Task 5: Security schemes and required permissions

**Files:**

- Create: `corehq/apps/api/openapi/security.py`
- Create: `corehq/apps/api/openapi/tests/test_security.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `SECURITY_SCHEMES: dict` — the `components.securitySchemes` block.
  - `SECURITY_REQUIREMENT: list[dict]` — the document-level `security` value.
  - `required_permission(resource) -> str | None` — the permission name a
    resource's authentication class demands.

`RequirePermissionAuthentication.__init__` stores its `HqPermissions` argument
on `self.permission`, so this is read from the instantiated resource's
`_meta.authentication`. `HqPermissions` members are described by their name,
e.g. `edit_commcare_users`.

- [ ] **Step 1: Write the failing test**

```python
from tastypie.authorization import ReadOnlyAuthorization

from corehq.apps.api.openapi.security import (
    SECURITY_REQUIREMENT,
    SECURITY_SCHEMES,
    required_permission,
)
from corehq.apps.api.resources.auth import (
    LoginAndDomainAuthentication,
    RequirePermissionAuthentication,
)
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.users.models import HqPermissions


class FakeMeta:
    def __init__(self, authentication):
        self.authentication = authentication


class FakeResource:
    def __init__(self, authentication):
        self._meta = FakeMeta(authentication)


def test_api_key_scheme_documents_the_header_format():
    api_key = SECURITY_SCHEMES['ApiKeyAuth']
    assert api_key['type'] == 'apiKey'
    assert api_key['in'] == 'header'
    assert api_key['name'] == 'Authorization'
    assert 'ApiKey <username>:<api_key>' in api_key['description']


def test_all_supported_schemes_are_declared():
    assert set(SECURITY_SCHEMES) == {
        'ApiKeyAuth',
        'BasicAuth',
        'DigestAuth',
        'OAuth2',
    }


def test_security_requirement_offers_every_scheme_as_an_alternative():
    assert SECURITY_REQUIREMENT == [
        {'ApiKeyAuth': []},
        {'BasicAuth': []},
        {'DigestAuth': []},
        {'OAuth2': ['access_apis']},
    ]


def test_required_permission_read_from_authentication_class():
    resource = FakeResource(
        RequirePermissionAuthentication(HqPermissions.edit_commcare_users)
    )
    assert required_permission(resource) == 'edit_commcare_users'


def test_no_required_permission_for_plain_authentication():
    assert required_permission(FakeResource(LoginAndDomainAuthentication())) is None


def test_real_resource_permission():
    from corehq.apps.api.resources import v0_5

    resource = v0_5.CommCareUserResource(api_name='v1')
    assert required_permission(resource) == 'edit_commcare_users'


def test_meta_default_authentication_has_no_permission():
    assert isinstance(CustomResourceMeta.authorization, ReadOnlyAuthorization)
    assert required_permission(FakeResource(CustomResourceMeta.authentication)) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_security.py -v`
Expected: FAIL —
`ModuleNotFoundError: No module named 'corehq.apps.api.openapi.security'`

- [ ] **Step 3: Write the implementation**

```python
"""Authentication schemes and permissions for the generated specs.

``corehq.apps.domain.decorators.api_auth`` accepts API key, Basic, Digest,
session and OAuth2 credentials. Session authentication is deliberately not
described: it is for the web UI, not for API clients.
"""
API_KEY_DESCRIPTION = (
    'Send the header `Authorization: ApiKey <username>:<api_key>`. '
    'Generate an API key from your CommCare HQ account settings.'
)

SECURITY_SCHEMES = {
    'ApiKeyAuth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': API_KEY_DESCRIPTION,
    },
    'BasicAuth': {
        'type': 'http',
        'scheme': 'basic',
        'description': 'HTTP Basic authentication with a CommCare HQ '
                       'username and password.',
    },
    'DigestAuth': {
        'type': 'http',
        'scheme': 'digest',
        'description': 'HTTP Digest authentication with a CommCare HQ '
                       'username and password.',
    },
    'OAuth2': {
        'type': 'oauth2',
        'description': 'OAuth2 with the `access_apis` scope.',
        'flows': {
            'authorizationCode': {
                'authorizationUrl': '/oauth/authorize/',
                'tokenUrl': '/oauth/token/',
                'scopes': {'access_apis': 'Access the CommCare APIs'},
            },
        },
    },
}

SECURITY_REQUIREMENT = [
    {'ApiKeyAuth': []},
    {'BasicAuth': []},
    {'DigestAuth': []},
    {'OAuth2': ['access_apis']},
]


def required_permission(resource):
    """The permission the resource's authentication class requires, if any."""
    authentication = getattr(resource._meta, 'authentication', None)
    permission = getattr(authentication, 'permission', None)
    if permission is None:
        return None
    return getattr(permission, 'name', str(permission))
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_security.py -v`
Expected: 7 passed.

If `test_required_permission_read_from_authentication_class` fails on the
permission's name, inspect what `HqPermissions.edit_commcare_users` actually is
(`uv run python -c` in a Django shell) and adjust `required_permission` to
produce the human-meaningful name — do not weaken the test to match a `repr`.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi
uv run ruff check corehq/apps/api/openapi
git add corehq/apps/api/openapi
git commit -m "Derive API security schemes and required permissions"
```

---

### Task 6: Paths, operations and parameters

**Files:**

- Create: `corehq/apps/api/openapi/operations.py`
- Create: `corehq/apps/api/openapi/tests/test_operations.py`

**Interfaces:**

- Consumes: `field_to_schema` (Task 4), `collect_docs` (Task 3),
  `required_permission` (Task 5), `ApiEntry` (Task 2).
- Produces:
  - `filter_parameters(filtering: dict) -> list[dict]`
  - `standard_list_parameters(resource_schema: dict) -> list[dict]`
  - `resource_paths(entry: ApiEntry) -> dict` — `{path: {method: operation}}`,
    where paths are `/a/{domain}/api/<name>/<version>/` and
    `.../{<detail_uri_name>}/` for domain scope, and `/api/...` for user scope.

Tastypie's `Meta.filtering` values are either a sequence of filter names
(`('exact', 'gte')`) or the `ALL` / `ALL_WITH_RELATIONS` integer constants.
`exact` produces a bare `field` parameter; any other filter name produces
`field__<filter>`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from tastypie.constants import ALL

from corehq.apps.api.openapi.catalogue import ApiEntry, USER
from corehq.apps.api.openapi.operations import (
    filter_parameters,
    resource_paths,
    standard_list_parameters,
)
from corehq.apps.api.resources import v0_5


def names(parameters):
    return [p['name'] for p in parameters]


def test_exact_filter_gives_a_bare_parameter():
    params = filter_parameters({'domain': ('exact',)})
    assert names(params) == ['domain']
    assert params[0]['in'] == 'query'
    assert params[0]['required'] is False


def test_comparison_filters_are_suffixed():
    params = filter_parameters({'date': ('exact', 'gt', 'lte')})
    assert names(params) == ['date', 'date__gt', 'date__lte']


def test_all_constant_gives_a_bare_parameter():
    assert names(filter_parameters({'name': ALL})) == ['name']


def test_filters_are_sorted_for_stable_output():
    params = filter_parameters({'b': ('exact',), 'a': ('exact',)})
    assert names(params) == ['a', 'b']


def test_standard_list_parameters():
    params = standard_list_parameters({'default_limit': 20})
    assert names(params) == ['limit', 'offset', 'format']
    limit = params[0]
    assert limit['schema']['default'] == 20
    assert limit['schema']['type'] == 'integer'


def test_order_by_is_added_when_the_resource_declares_ordering():
    params = standard_list_parameters(
        {'default_limit': 20, 'ordering': ['date_modified']}
    )
    assert names(params) == ['limit', 'offset', 'format', 'order_by']
    order_by = params[-1]
    assert order_by['schema']['enum'] == [
        'date_modified', '-date_modified',
    ]


def test_domain_resource_paths():
    """v0_5.CommCareUserResource allows GET/POST on the list and
    GET/PUT/DELETE on the detail endpoint."""
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    assert set(paths) == {
        '/a/{domain}/api/user/v1/',
        '/a/{domain}/api/user/v1/{pk}/',
    }
    assert set(paths['/a/{domain}/api/user/v1/']) == {
        'get', 'post', 'parameters',
    }
    assert set(paths['/a/{domain}/api/user/v1/{pk}/']) == {
        'get', 'put', 'delete', 'parameters',
    }


def test_list_endpoint_with_no_detail_methods_omits_the_detail_path():
    entry = ApiEntry(v0_5.IdentityResource, 'v1', 'identity-v1', scope=USER)
    paths = resource_paths(entry)
    assert set(paths) == {'/api/identity/v1/'}


def test_domain_is_a_required_path_parameter():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    path_params = paths['/a/{domain}/api/user/v1/']['parameters']
    domain = next(p for p in path_params if p['name'] == 'domain')
    assert domain['in'] == 'path'
    assert domain['required'] is True


def test_user_scoped_paths_have_no_domain():
    entry = ApiEntry(v0_5.IdentityResource, 'v1', 'identity-v1', scope=USER)
    paths = resource_paths(entry)
    assert all(not p.startswith('/a/') for p in paths)
    assert '/api/identity/v1/' in paths


def test_operation_lists_the_required_permission():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    operation = resource_paths(entry)['/a/{domain}/api/user/v1/']['get']
    assert 'edit_commcare_users' in operation['description']


def test_write_methods_carry_a_request_body_of_writable_fields():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    post = paths['/a/{domain}/api/user/v1/']['post']
    schema = post['requestBody']['content']['application/json']['schema']
    assert schema['type'] == 'object'
    assert 'username' in schema['properties']
    assert 'id' not in schema['properties'], (
        'read-only fields must not appear in request bodies'
    )


def test_read_methods_have_no_request_body():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    get = resource_paths(entry)['/a/{domain}/api/user/v1/']['get']
    assert 'requestBody' not in get


def test_delete_has_no_request_body():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    delete = paths['/a/{domain}/api/user/v1/{pk}/']['delete']
    assert 'requestBody' not in delete


@pytest.mark.parametrize('resource_cls, version', [
    (v0_5.GroupResource, 'v1'),
    (v0_5.WebUserResource, 'v1'),
    (v0_5.BulkUserResource, 'v1'),
])
def test_paths_generate_without_error_for_other_resources(resource_cls, version):
    paths = resource_paths(ApiEntry(resource_cls, version, 'slug'))
    assert paths
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_operations.py -v`
Expected: FAIL —
`ModuleNotFoundError: No module named 'corehq.apps.api.openapi.operations'`

- [ ] **Step 3: Write the implementation**

```python
"""Generation of OpenAPI paths, operations and parameters for a resource."""
from tastypie.constants import ALL, ALL_WITH_RELATIONS

from corehq.apps.api.openapi.catalogue import USER
from corehq.apps.api.openapi.docs import collect_docs
from corehq.apps.api.openapi.schema import field_to_schema
from corehq.apps.api.openapi.security import required_permission

DOMAIN_PARAMETER = {
    'name': 'domain',
    'in': 'path',
    'required': True,
    'description': 'The project space (domain) name.',
    'schema': {'type': 'string'},
}


def filter_parameters(filtering):
    """Query parameters for a resource's ``Meta.filtering`` declaration."""
    parameters = []
    for field_name in sorted(filtering):
        filters = filtering[field_name]
        if filters in (ALL, ALL_WITH_RELATIONS):
            filters = ('exact',)
        for filter_name in filters:
            name = (
                field_name
                if filter_name == 'exact'
                else f'{field_name}__{filter_name}'
            )
            parameters.append({
                'name': name,
                'in': 'query',
                'required': False,
                'schema': {'type': 'string'},
            })
    return parameters


def standard_list_parameters(resource_schema):
    """The pagination and format parameters every list endpoint accepts."""
    parameters = [
        {
            'name': 'limit',
            'in': 'query',
            'required': False,
            'description': 'Maximum number of records to return. '
                           'Use 0 to request all records.',
            'schema': {
                'type': 'integer',
                'default': resource_schema['default_limit'],
            },
        },
        {
            'name': 'offset',
            'in': 'query',
            'required': False,
            'description': 'Number of records to skip.',
            'schema': {'type': 'integer', 'default': 0},
        },
        {
            'name': 'format',
            'in': 'query',
            'required': False,
            'description': 'Response format.',
            'schema': {
                'type': 'string',
                'enum': ['json', 'xml'],
                'default': 'json',
            },
        },
    ]
    ordering = resource_schema.get('ordering')
    if ordering:
        enum = [field for field in ordering]
        enum += [f'-{field}' for field in ordering]
        parameters.append({
            'name': 'order_by',
            'in': 'query',
            'required': False,
            'description': 'Field to sort by. Prefix with "-" to reverse.',
            'schema': {'type': 'string', 'enum': enum},
        })
    return parameters


def object_schema(resource_schema, docs):
    """The schema for a single object returned by the resource."""
    field_schemas = docs.get('field_schemas', {})
    properties = {
        name: field_to_schema(info, override=field_schemas.get(name))
        for name, info in resource_schema['fields'].items()
    }
    return {'type': 'object', 'properties': properties}


def request_schema(resource_schema, docs):
    """The schema a write request accepts: the writable fields only."""
    field_schemas = docs.get('field_schemas', {})
    properties = {
        name: field_to_schema(info, override=field_schemas.get(name))
        for name, info in resource_schema['fields'].items()
        if not info.get('readonly')
    }
    return {'type': 'object', 'properties': properties}


def _description(docs, resource):
    parts = []
    if docs.get('description'):
        parts.append(docs['description'].strip())
    permission = docs.get('permissions') or required_permission(resource)
    if permission:
        parts.append(f'Requires the `{permission}` permission.')
    return '\n\n'.join(parts)


def resource_paths(entry):
    """OpenAPI path items for one catalogue entry."""
    resource = entry.resource(api_name=entry.version)
    resource_schema = resource.build_schema()
    docs = collect_docs(entry.resource)

    name = resource._meta.resource_name
    prefix = '/api' if entry.scope == USER else '/a/{domain}/api'
    base = f'{prefix}/{name}/{entry.version}/'
    detail_key = resource._meta.detail_uri_name
    detail = f'{base}{{{detail_key}}}/'

    path_parameters = [] if entry.scope == USER else [DOMAIN_PARAMETER]
    summary = docs.get('summary') or name.replace('_', ' ').title()
    description = _description(docs, resource)
    schema = object_schema(resource_schema, docs)
    write_schema = request_schema(resource_schema, docs)

    paths = {}

    list_methods = resource_schema['allowed_list_http_methods']
    if list_methods:
        item = {'parameters': list(path_parameters)}
        for method in list_methods:
            operation = {
                'summary': summary,
                'operationId': f'{name}_{entry.version}_list_{method}',
                'tags': [name],
                'responses': _list_responses(schema),
            }
            if description:
                operation['description'] = description
            if method == 'get':
                operation['parameters'] = (
                    standard_list_parameters(resource_schema)
                    + filter_parameters(resource_schema.get('filtering', {}))
                )
            else:
                operation['requestBody'] = _request_body(write_schema)
            item[method] = operation
        paths[base] = item

    detail_methods = resource_schema['allowed_detail_http_methods']
    if detail_methods:
        item = {
            'parameters': list(path_parameters) + [{
                'name': detail_key,
                'in': 'path',
                'required': True,
                'description': 'Unique identifier of the record.',
                'schema': {'type': 'string'},
            }],
        }
        for method in detail_methods:
            operation = {
                'summary': summary,
                'operationId': f'{name}_{entry.version}_detail_{method}',
                'tags': [name],
                'responses': {
                    '200': {
                        'description': 'The requested record.',
                        'content': {'application/json': {'schema': schema}},
                    },
                },
            }
            if description:
                operation['description'] = description
            if method in ('put', 'patch'):
                operation['requestBody'] = _request_body(write_schema)
            item[method] = operation
        paths[detail] = item

    return paths


def _request_body(schema):
    return {
        'required': True,
        'content': {'application/json': {'schema': schema}},
    }


def _list_responses(schema):
    return {
        '200': {
            'description': 'A page of records.',
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'meta': {
                                '$ref': '#/components/schemas/'
                                        'PaginationMeta',
                            },
                            'objects': {'type': 'array', 'items': schema},
                        },
                    },
                },
            },
        },
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_operations.py -v`
Expected: all tests in the file pass. If an allowed-methods assertion fails,
check the resource's `Meta.list_allowed_methods` / `detail_allowed_methods` —
the assertions encode what those are today, and a mismatch means either the
resource changed or the generator is wrong. Do not loosen the assertion without
establishing which.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi
uv run ruff check corehq/apps/api/openapi
git add corehq/apps/api/openapi
git commit -m "Generate OpenAPI paths and parameters for API resources"
```

---

### Task 7: Document assembly

**Files:**

- Create: `corehq/apps/api/openapi/builder.py`
- Create: `corehq/apps/api/openapi/tests/test_builder.py`
- Modify: `pyproject.toml` (add `openapi-spec-validator` to the `test` group)

**Interfaces:**

- Consumes: `resource_paths` (Task 6), `SECURITY_SCHEMES` /
  `SECURITY_REQUIREMENT` (Task 5), `documented_entries` (Task 2).
- Produces:

  - `OPENAPI_VERSION = '3.0.3'`
  - `PAGINATION_META_SCHEMA: dict`
  - `build_document(entries: list[ApiEntry], *, title: str) -> dict`
  - `build_all() -> dict[str, dict]` — `{doc_slug: document}` for each
    documented entry, plus `'bundle'` covering all of them.

- [ ] **Step 1: Write the failing test**

```python
from openapi_spec_validator import validate

from corehq.apps.api.openapi.builder import (
    OPENAPI_VERSION,
    build_all,
    build_document,
)
from corehq.apps.api.openapi.catalogue import ApiEntry, documented_entries
from corehq.apps.api.resources import v0_5


def test_document_shape():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    doc = build_document([entry], title='Mobile Workers')
    assert doc['openapi'] == OPENAPI_VERSION == '3.0.3'
    assert doc['info']['title'] == 'Mobile Workers'
    assert doc['servers'][0]['url']
    assert '/a/{domain}/api/user/v1/' in doc['paths']
    assert 'PaginationMeta' in doc['components']['schemas']
    assert doc['components']['securitySchemes']
    assert doc['security']


def test_pagination_meta_is_referenced_and_defined():
    doc = build_document(
        [ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')],
        title='Mobile Workers',
    )
    meta = doc['components']['schemas']['PaginationMeta']
    assert set(meta['properties']) == {
        'limit', 'offset', 'total_count', 'next', 'previous',
    }


def test_document_validates_against_openapi_30():
    doc = build_document(
        [ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')],
        title='Mobile Workers',
    )
    validate(doc)


def test_build_all_produces_a_document_per_slug_plus_a_bundle():
    documents = build_all()
    slugs = {entry.doc_slug for entry in documented_entries()}
    # Task 13 adds view-based documents (case-v2), so this is a subset
    # relationship rather than equality.
    assert slugs | {'bundle'} <= set(documents)


def test_every_generated_document_validates():
    for name, doc in build_all().items():
        try:
            validate(doc)
        except Exception as exc:
            raise AssertionError(f'{name} is not valid OpenAPI: {exc}')


def test_bundle_contains_every_documented_path():
    documents = build_all()
    bundle_paths = set(documents['bundle']['paths'])
    for slug, doc in documents.items():
        if slug == 'bundle':
            continue
        assert set(doc['paths']) <= bundle_paths
```

- [ ] **Step 2: Add the validator dependency**

In `pyproject.toml`, add `'openapi-spec-validator'` to the `test` list inside
`[dependency-groups]`, then sync:

```bash
uv sync --compile-bytecode && uv pip install -r requirements/local.txt
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_builder.py -v`
Expected: FAIL —
`ModuleNotFoundError: No module named 'corehq.apps.api.openapi.builder'`

- [ ] **Step 4: Write the implementation**

```python
"""Assembly of complete OpenAPI documents for the CommCare data APIs."""
from corehq.apps.api.openapi.catalogue import documented_entries
from corehq.apps.api.openapi.operations import resource_paths
from corehq.apps.api.openapi.security import (
    SECURITY_REQUIREMENT,
    SECURITY_SCHEMES,
)

OPENAPI_VERSION = '3.0.3'

SERVERS = [{
    'url': 'https://{host}',
    'description': 'A CommCare HQ instance.',
    'variables': {
        'host': {
            'default': 'www.commcarehq.org',
            'description': 'Hostname of the CommCare HQ instance.',
        },
    },
}]

PAGINATION_META_SCHEMA = {
    'type': 'object',
    'description': 'Pagination metadata for a page of records.',
    'properties': {
        'limit': {'type': 'integer'},
        'offset': {'type': 'integer'},
        'total_count': {'type': 'integer'},
        'next': {'type': 'string', 'nullable': True},
        'previous': {'type': 'string', 'nullable': True},
    },
}


def build_document(entries, *, title):
    paths = {}
    for entry in entries:
        paths.update(resource_paths(entry))
    return {
        'openapi': OPENAPI_VERSION,
        'info': {
            'title': title,
            'version': '1.0.0',
            'description': 'CommCare data API.',
        },
        'servers': SERVERS,
        'paths': paths,
        'components': {
            'schemas': {'PaginationMeta': PAGINATION_META_SCHEMA},
            'securitySchemes': SECURITY_SCHEMES,
        },
        'security': SECURITY_REQUIREMENT,
    }


def _title(entry):
    from corehq.apps.api.openapi.docs import collect_docs

    docs = collect_docs(entry.resource)
    if docs.get('summary'):
        return docs['summary']
    return entry.doc_slug.replace('-', ' ').title()


def build_all():
    """Every documented spec, keyed by ``doc_slug``, plus ``'bundle'``."""
    entries = documented_entries()
    documents = {
        entry.doc_slug: build_document([entry], title=_title(entry))
        for entry in entries
    }
    documents['bundle'] = build_document(
        entries, title='CommCare Data APIs'
    )
    return documents
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_builder.py -v`
Expected: 6 passed.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi
uv run ruff check corehq/apps/api/openapi pyproject.toml
git add corehq/apps/api/openapi pyproject.toml uv.lock
git commit -m "Assemble validated OpenAPI documents for documented APIs"
```

---

### Task 8: Management command and committed artifacts

**Files:**

- Create: `corehq/apps/api/openapi/management/__init__.py`
- Create: `corehq/apps/api/openapi/management/commands/__init__.py`
- Create: `corehq/apps/api/openapi/management/commands/generate_openapi.py`
- Create: `corehq/apps/api/openapi/tests/test_generate_openapi.py`
- Create: `docs/api/spec/*.json` (generated output, committed)

**Interfaces:**

- Consumes: `build_all` (Task 7).
- Produces:

  - `SPEC_DIR: pathlib.Path` — `<repo>/docs/api/spec`
  - `write_specs(spec_dir: Path) -> list[Path]`
  - `serialize(document: dict) -> str` — deterministic JSON, sorted keys,
    2-space indent, trailing newline.
  - Management command `generate_openapi`, with `--check` to fail on drift
    instead of writing.

- [ ] **Step 1: Write the failing test**

```python
import json

from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.openapi.management.commands.generate_openapi import (
    SPEC_DIR,
    serialize,
    write_specs,
)


def test_serialize_is_deterministic_and_sorted():
    document = {'b': 1, 'a': {'d': 2, 'c': 3}}
    text = serialize(document)
    assert text.startswith('{\n')
    assert text.endswith('\n')
    assert text.index('"a"') < text.index('"b"')
    assert serialize(document) == text


def test_write_specs_writes_one_file_per_document(tmp_path):
    written = write_specs(tmp_path)
    assert {path.name for path in written} == {
        f'{name}.json' for name in build_all()
    }
    for path in written:
        json.loads(path.read_text())


def test_committed_specs_are_up_to_date():
    """Regeneration must be a no-op. If this fails, run:

        ./manage.py generate_openapi
    """
    for name, document in build_all().items():
        path = SPEC_DIR / f'{name}.json'
        assert path.exists(), f'missing committed spec: {path}'
        assert path.read_text() == serialize(document), (
            f'{path} is stale; run ./manage.py generate_openapi'
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_generate_openapi.py -v`
Expected: FAIL — `ModuleNotFoundError` for the command module.

- [ ] **Step 3: Write the command**

Create the two empty `__init__.py` files, then the command:

```python
"""Write the committed OpenAPI specs for the CommCare data APIs."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

import settings

from corehq.apps.api.openapi.builder import build_all

SPEC_DIR = Path(settings.BASE_DIR) / 'docs' / 'api' / 'spec'


def serialize(document):
    """Deterministic JSON, so that regeneration produces no spurious diff."""
    return json.dumps(document, indent=2, sort_keys=True) + '\n'


def write_specs(spec_dir):
    spec_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, document in build_all().items():
        path = spec_dir / f'{name}.json'
        path.write_text(serialize(document))
        written.append(path)
    return written


class Command(BaseCommand):
    help = 'Generate the OpenAPI specs for the CommCare data APIs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Exit non-zero if the committed specs are out of date, '
                 'without writing anything.',
        )

    def handle(self, **options):
        if options['check']:
            stale = [
                name
                for name, document in build_all().items()
                if not (SPEC_DIR / f'{name}.json').exists()
                or (SPEC_DIR / f'{name}.json').read_text()
                != serialize(document)
            ]
            if stale:
                raise CommandError(
                    'These specs are out of date: '
                    + ', '.join(sorted(stale))
                    + '. Run ./manage.py generate_openapi.'
                )
            self.stdout.write('OpenAPI specs are up to date.')
            return
        for path in write_specs(SPEC_DIR):
            self.stdout.write(f'wrote {path}')
```

`settings.BASE_DIR` is defined at `settings.py:24` and is the repository root.
If for some reason it is unavailable, use `Path(__file__).resolve().parents[5]`
and verify it points at the repository root before committing.

- [ ] **Step 4: Generate the artifacts**

Run: `uv run ./manage.py generate_openapi` Expected: one `wrote ...` line per
documented slug, plus `bundle.json`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/ -v` Expected: all
pass, including `test_committed_specs_are_up_to_date`.

- [ ] **Step 6: Verify the check mode detects drift**

```bash
uv run ./manage.py generate_openapi --check   # expect: up to date
printf '{}\n' > docs/api/spec/bundle.json
uv run ./manage.py generate_openapi --check   # expect: CommandError
uv run ./manage.py generate_openapi           # restore
```

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi
uv run ruff check corehq/apps/api/openapi
git add corehq/apps/api/openapi docs/api/spec
git commit -m "Add generate_openapi command and committed specs

The specs are committed so a change to a resource's shape shows up as a
reviewable diff. ./manage.py generate_openapi --check fails on drift."
```

---

### Task 9: Document the mobile worker API in code

This is the first content-authoring task, and the template for Tasks 11 and 12.
Source material: the existing `docs/api/list-mobile-workers.rst` and
`docs/api/mobile-worker.rst`, whose field tables and JSON sample move into
`help_text`, `Docs`, and an example file.

**Files:**

- Modify: `corehq/apps/api/resources/v0_1.py` (`UserResource`,
  `CommCareUserResource`)
- Modify: `corehq/apps/api/resources/v0_5.py` (`CommCareUserResource`)
- Create: `corehq/apps/api/openapi/examples/user/v1/list_response.json`
- Create: `corehq/apps/api/openapi/tests/test_documented_fields.py`
- Modify: `docs/api/spec/*.json` (regenerated)

**Interfaces:**

- Consumes: `collect_docs`, `field_description`, `documented_entries`.
- Produces: `DOCUMENTED_SLUGS: frozenset[str]` in `test_documented_fields.py` —
  the slugs currently held to the every-field-documented standard. Tasks 11–13
  add to it.

- [ ] **Step 1: Write the failing test**

```python
from corehq.apps.api.openapi.catalogue import documented_entries
from corehq.apps.api.openapi.docs import collect_docs, field_description

# Slugs whose fields must all carry a real description. Add a slug here when
# its documentation is written; do not remove one.
DOCUMENTED_SLUGS = frozenset({'user-v1'})


def _undocumented_fields(entry):
    resource = entry.resource(api_name=entry.version)
    schema = resource.build_schema()
    overrides = collect_docs(entry.resource).get('field_schemas', {})
    return sorted(
        name
        for name, info in schema['fields'].items()
        if not field_description(info.get('help_text'))
        and 'description' not in overrides.get(name, {})
    )


def test_every_field_of_documented_apis_has_a_description():
    failures = {}
    for entry in documented_entries():
        if entry.doc_slug not in DOCUMENTED_SLUGS:
            continue
        undocumented = _undocumented_fields(entry)
        if undocumented:
            failures[entry.doc_slug] = undocumented
    assert not failures, (
        'These fields need help_text (or a Docs.field_schemas description): '
        f'{failures}'
    )


def test_documented_apis_declare_a_summary_and_description():
    for entry in documented_entries():
        if entry.doc_slug not in DOCUMENTED_SLUGS:
            continue
        docs = collect_docs(entry.resource)
        assert docs.get('summary'), f'{entry.doc_slug} needs a Docs.summary'
        assert docs.get('description'), (
            f'{entry.doc_slug} needs a Docs.description'
        )


def test_declared_examples_exist_on_disk():
    from pathlib import Path

    from corehq.apps.api import openapi

    examples_dir = Path(openapi.__file__).parent / 'examples'
    for entry in documented_entries():
        for name, relative in collect_docs(entry.resource).get(
            'examples', {}
        ).items():
            assert (examples_dir / relative).exists(), (
                f'{entry.doc_slug} example {name!r} missing: {relative}'
            )
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_documented_fields.py -v`
Expected: FAIL — every `user-v1` field is listed as undocumented, and the
summary assertion fails.

- [ ] **Step 3: Add `help_text` to the user resource fields**

In `corehq/apps/api/resources/v0_1.py`, add `help_text` to each field of
`UserResource` and `CommCareUserResource`. Descriptions come from the table in
`docs/api/list-mobile-workers.rst`.

```python
class UserResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    type = "user"
    id = fields.CharField(
        attribute='get_id',
        readonly=True,
        unique=True,
        help_text='Unique identifier of the user.',
    )
    username = fields.CharField(
        attribute='username',
        unique=True,
        help_text='Username of the user, including the domain suffix, '
                  'for example "jdoe@example.commcarehq.org".',
    )
    first_name = fields.CharField(
        attribute='first_name',
        null=True,
        help_text='First name of the user.',
    )
    last_name = fields.CharField(
        attribute='last_name',
        null=True,
        help_text='Last name of the user.',
    )
    default_phone_number = fields.CharField(
        attribute='default_phone_number',
        null=True,
        help_text='Primary phone number of the user, in international '
                  'format.',
    )
    email = fields.CharField(
        attribute='email',
        help_text='Email address of the user.',
    )
    phone_numbers = fields.ListField(
        attribute='phone_numbers',
        help_text='All phone numbers registered for the user.',
    )
    eulas = fields.CharField(
        attribute='eulas',
        null=True,
        help_text='End-user licence agreements the user has accepted.',
    )
```

```python
class CommCareUserResource(UserResource):
    groups = fields.ListField(
        attribute='get_group_ids',
        help_text='Identifiers of the groups the user belongs to.',
    )
    user_data = fields.DictField(
        help_text='Custom user data fields defined for the project space.',
    )
```

Do not change any other field argument. Run the existing user API tests after
this step to confirm nothing else moved:

Run: `uv run pytest --reusedb=1 corehq/apps/api/tests/test_user_resources.py -v`
Expected: same result as before your change.

- [ ] **Step 4: Add the remaining field descriptions and the `Docs` class**

Inspect what `user-v1` still reports as undocumented:

```bash
uv run pytest --reusedb=1 \
  corehq/apps/api/openapi/tests/test_documented_fields.py -v
```

The failure message lists the remaining field names — these are the ones
declared on `v0_5.CommCareUserResource` (such as `primary_location`,
`locations`, `resource_uri`). Add `help_text` to each, using
`docs/api/list-mobile-workers.rst` for wording, then add the `Docs` class and
container schemas to `v0_5.CommCareUserResource`:

```python
class CommCareUserResource(v0_1.CommCareUserResource):

    class Docs:
        summary = 'Mobile Workers'
        description = (
            'List mobile workers in a project space, or fetch a single '
            'mobile worker by identifier. Mobile workers are the users '
            'who submit forms from CommCare mobile or web apps.'
        )
        examples = {'list_response': 'user/v1/list_response.json'}
        field_schemas = {
            'phone_numbers': {
                'items': {'type': 'string'},
                'description': 'All phone numbers registered for the user.',
            },
            'groups': {
                'items': {'type': 'string'},
                'description': 'Identifiers of the groups the user '
                               'belongs to.',
            },
            'locations': {
                'items': {'type': 'string'},
                'description': 'Identifiers of the locations the user is '
                               'assigned to.',
            },
            'user_data': {
                'additionalProperties': {'type': 'string'},
                'description': 'Custom user data fields defined for the '
                               'project space.',
            },
        }
```

- [ ] **Step 5: Add the example response**

Create `corehq/apps/api/openapi/examples/user/v1/list_response.json`, taken from
the sample output in `docs/api/list-mobile-workers.rst`:

```json
{
  "meta": {
    "limit": 2,
    "next": null,
    "offset": 0,
    "previous": null,
    "total_count": 29
  },
  "objects": [
    {
      "type": "user",
      "id": "3c5a623af057e23a32ae4000cf291339",
      "username": "jdoe@example.commcarehq.org",
      "first_name": "John",
      "last_name": "Doe",
      "default_phone_number": "+50253311399",
      "email": "jdoe@example.org",
      "phone_numbers": ["+50253311399", "+50253314588"],
      "groups": ["9a0accdba29e01a61ea099394737c4fb"],
      "locations": ["26fc44e2792b4f2fa8ef86178f0a958e"],
      "primary_location": "26fc44e2792b4f2fa8ef86178f0a958e",
      "user_data": { "chw_id": "13/43/DFA" }
    }
  ]
}
```

- [ ] **Step 6: Wire examples into the generated spec**

In `corehq/apps/api/openapi/operations.py`, load declared examples and attach
them to the list response. Add near the top:

```python
import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent / 'examples'


def load_example(relative_path):
    return json.loads((EXAMPLES_DIR / relative_path).read_text())
```

Then, in `resource_paths`, replace the inline
`'responses': _list_responses(schema)` in the list operation with a `responses`
local that has the example attached. Leave the
`else: operation['requestBody'] = ...` branch from Task 6 exactly as it is:

```python
            responses = _list_responses(schema)
            example = docs.get('examples', {}).get('list_response')
            if example:
                responses['200']['content']['application/json'][
                    'example'
                ] = load_example(example)
            operation = {
                'summary': summary,
                'operationId': f'{name}_{entry.version}_list_{method}',
                'tags': [name],
                'responses': responses,
            }
```

Add a test for this in `corehq/apps/api/openapi/tests/test_operations.py`:

```python
def test_declared_list_example_is_attached():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    operation = resource_paths(entry)['/a/{domain}/api/user/v1/']['get']
    content = operation['responses']['200']['content']['application/json']
    assert content['example']['objects'][0]['username']
```

- [ ] **Step 7: Regenerate and run all the openapi tests**

```bash
uv run ./manage.py generate_openapi
uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/ -v
```

Expected: all pass, including the documented-fields and no-drift tests.

- [ ] **Step 8: Lint and commit**

```bash
uv run ruff format corehq/apps/api corehq/apps/api/openapi
uv run ruff check corehq/apps/api corehq/apps/api/openapi
git add corehq/apps/api docs/api/spec
git commit -m "Document the mobile worker API in code

Field descriptions become help_text, endpoint narrative becomes a Docs inner
class, and the sample response moves to an example file. A test holds every
field of a documented API to having a real description."
```

---

### Task 10: Render the specs on readthedocs

**Files:**

- Modify: `pyproject.toml` (add `sphinxcontrib-openapi` to the `docs` group)
- Modify: `docs/conf.py`
- Modify: `docs/api/list-mobile-workers.rst`
- Modify: `docs/api/mobile-worker.rst`

**Interfaces:**

- Consumes: `docs/api/spec/user-v1.json` (Task 8).
- Produces: the documentation build pattern that Tasks 11–13 follow.

- [ ] **Step 1: Confirm the renderer accepts OpenAPI 3.0.3**

This is the open risk flagged in the spec. Resolve it before editing pages.

```bash
uv add --group docs sphinxcontrib-openapi
uv run python -c "
import json, sphinxcontrib.openapi as ext
print('version:', ext.__version__ if hasattr(ext, \"__version__\") else 'n/a')
spec = json.load(open('docs/api/spec/user-v1.json'))
print('spec openapi:', spec['openapi'])
"
```

Then build the docs (Step 4) and inspect the output. If 3.0.3 is not rendered,
stop and report: the fallback is `sphinxcontrib-redoc` over
`docs/api/spec/bundle.json`, which changes only this task.

- [ ] **Step 2: Register the extension**

In `docs/conf.py`, add to `extensions`:

```python
extensions = [
    'myst_parser',
    'sphinx.ext.viewcode',
    'sphinxcontrib_django',
    'sphinxcontrib.openapi',
    'sphinx_rtd_theme',
]
```

- [ ] **Step 3: Convert the two mobile worker pages**

Replace the body of `docs/api/list-mobile-workers.rst` with the directive.
`:examples:` is required for the sample response to render at all.

```rst
List Mobile Workers
===================

.. openapi:: spec/user-v1.json
   :examples:
   :include:
      /a/\{domain\}/api/user/v1/$
```

And `docs/api/mobile-worker.rst`, which documents the single-user endpoint:

```rst
Mobile Worker
=============

.. openapi:: spec/user-v1.json
   :examples:
   :include:
      /a/\{domain\}/api/user/v1/\{pk\}/
```

If `:include:` regex escaping proves awkward with the braces, use `:paths:` with
the literal path instead:

```rst
.. openapi:: spec/user-v1.json
   :examples:
   :paths:
      /a/{domain}/api/user/v1/
```

- [ ] **Step 4: Build the docs and inspect the result**

```bash
cd docs && uv run make html && cd ..
python -m http.server --directory docs/_build/html 8001
```

Open `http://localhost:8001/api/list-mobile-workers.html`. Confirm: the
endpoint, its parameters (`limit`, `offset`, `format`), the response fields with
their descriptions, and the sample JSON all render. Confirm no Sphinx warnings
about the spec.

- [ ] **Step 5: Commit**

```bash
uv run ruff check docs/conf.py
git add pyproject.toml uv.lock docs/conf.py docs/api/list-mobile-workers.rst \
  docs/api/mobile-worker.rst
git commit -m "Render the mobile worker API docs from its OpenAPI spec"
```

---

### Task 11: Document the case, form and group APIs

Same pattern as Task 9, for three more resources. Source material:
`docs/api/cases-v1.rst`, `docs/api/form-data.rst`, `docs/api/list-forms.rst`,
`docs/api/list-groups.rst`, `docs/api/user-group.rst`.

**Files:**

- Modify: `corehq/apps/api/resources/v0_3.py`, `v0_4.py` (case, form, group
  fields and `Docs`)
- Create: `corehq/apps/api/openapi/examples/case/v1/list_response.json`
- Create: `corehq/apps/api/openapi/examples/form/v1/list_response.json`
- Create: `corehq/apps/api/openapi/examples/group/v1/list_response.json`
- Modify: `corehq/apps/api/openapi/tests/test_documented_fields.py`
- Modify: `docs/api/cases-v1.rst`, `form-data.rst`, `list-forms.rst`,
  `list-groups.rst`, `user-group.rst`
- Modify: `docs/api/spec/*.json`

**Interfaces:**

- Consumes: everything from Tasks 3–10.
- Produces: nothing new; extends `DOCUMENTED_SLUGS`.

- [ ] **Step 1: Extend the documented-slugs set to make the test fail**

```python
DOCUMENTED_SLUGS = frozenset({
    'user-v1',
    'case-v1',
    'form-v1',
    'group-v1',
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_documented_fields.py -v`
Expected: FAIL, listing the undocumented fields of the case, form and group
resources.

- [ ] **Step 3: Add `help_text` and `Docs` for each resource**

Work one resource at a time, using the failure list as your checklist. For each:
add `help_text=` to every field the test names, then a `Docs` class. Take
wording from the corresponding RST page's output-field table. Note that
`v0_4.CommCareCaseResource` inherits fields from `v0_3.CommCareCaseResource`, so
descriptions belong on whichever class declares each field.

Note the `UseIfRequested`-wrapped fields on `v0_4.CommCareCaseResource`
(`xforms_by_name`, `xforms_by_xmlns`, `child_cases`, `parent_cases`): that
wrapper delegates attribute access to the underlying field, so pass `help_text`
to the field it wraps, and say in the description that the field is returned
only when `<field>__full=true` is passed.

```python
    child_cases = UseIfRequested(
        ToManyDictField(
            'corehq.apps.api.resources.v0_4.CommCareCaseResource',
            attribute='child_cases',
            help_text='Child cases of this case, keyed by index name. '
                      'Returned only when child_cases__full=true is '
                      'passed.',
        )
    )
```

Example `Docs` for the group resource:

```python
    class Docs:
        summary = 'Groups'
        description = (
            'List the groups in a project space, or fetch a single group '
            'by identifier. Groups collect mobile workers for case '
            'sharing and reporting.'
        )
        examples = {'list_response': 'group/v1/list_response.json'}
        field_schemas = {
            'users': {
                'items': {'type': 'string'},
                'description': 'Identifiers of the users in this group.',
            },
            'metadata': {
                'additionalProperties': True,
                'description': 'Custom metadata stored on the group.',
            },
        }
```

- [ ] **Step 4: Add the three example files**

Copy each sample JSON response from the matching RST page into
`corehq/apps/api/openapi/examples/<resource>/v1/list_response.json`. Validate
each parses:

```bash
for f in corehq/apps/api/openapi/examples/*/v1/list_response.json; do
  python -c "import json,sys; json.load(open('$f'))" || echo "BAD: $f"
done
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/ -v
uv run pytest --reusedb=1 corehq/apps/api/tests/case_resources.py \
  corehq/apps/api/tests/form_resources.py \
  corehq/apps/api/tests/group_resources.py -v
```

Expected: openapi tests pass; the existing resource tests are unchanged.

- [ ] **Step 6: Convert the RST pages and regenerate**

Follow the Task 10 pattern for `cases-v1.rst`, `form-data.rst`,
`list-forms.rst`, `list-groups.rst` and `user-group.rst`, pointing each at
`spec/case-v1.json`, `spec/form-v1.json` or `spec/group-v1.json` and filtering
to the list or detail path as the page requires.

```bash
uv run ./manage.py generate_openapi
cd docs && uv run make html && cd ..
```

Expected: no Sphinx warnings; each page renders its endpoint.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff format corehq/apps/api
uv run ruff check corehq/apps/api
git add corehq/apps/api docs/api
git commit -m "Document the case, form and group APIs in code"
```

---

### Task 12: Document the location, location type and lookup table APIs

Same pattern again, covering the two location versions — which is where the
inheritance-based documentation pays off, since `v0_6.LocationResource` extends
`v0_5.LocationResource`.

**Files:**

- Modify: `corehq/apps/locations/resources/v0_5.py`, `v0_6.py`
- Modify: `corehq/apps/fixtures/resources/v0_1.py`, `v0_6.py`
- Create: `corehq/apps/api/openapi/examples/location/v1/list_response.json`
- Create: `corehq/apps/api/openapi/examples/location/v2/list_response.json`
- Create: `corehq/apps/api/openapi/examples/lookup_table/v1/list_response.json`
- Modify: `corehq/apps/api/openapi/tests/test_documented_fields.py`
- Modify: `docs/api/locations-v1.rst`, `locations-v2.rst`, `location-types.rst`,
  `fixture.rst`
- Modify: `docs/api/spec/*.json`

**Interfaces:**

- Consumes: everything from Tasks 3–10.
- Produces: nothing new; extends `DOCUMENTED_SLUGS`.

- [ ] **Step 1: Extend the documented-slugs set to make the test fail**

```python
DOCUMENTED_SLUGS = frozenset({
    'user-v1',
    'case-v1',
    'form-v1',
    'group-v1',
    'location-v1',
    'location-v2',
    'location-type-v1',
    'lookup-table-v1',
    'lookup-table-item-v1',
    'lookup-table-item-v2',
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_documented_fields.py -v`
Expected: FAIL, listing undocumented fields for each of the six slugs.

- [ ] **Step 3: Document the shared fields once, on the base classes**

Add `help_text` on `locations.v0_5.BaseLocationsResource` and
`locations.v0_5.LocationResource` — `v0_6.LocationResource` inherits them. Add a
`Docs` class to `v0_5.LocationResource`, and on `v0_6.LocationResource` add only
what differs:

```python
class LocationResource(v0_5.LocationResource):

    class Docs:
        summary = 'Locations (v2)'
        description = (
            'List locations in a project space, create locations, or '
            'fetch and update a single location. Version 2 returns '
            'location data as a nested object and supports filtering by '
            'last modified date.'
        )
        examples = {'list_response': 'location/v2/list_response.json'}
```

Confirm the inheritance actually works before moving on:

```bash
uv run python -c "
from corehq.apps.api.openapi.docs import collect_docs
from corehq.apps.locations.resources import v0_6
docs = collect_docs(v0_6.LocationResource)
print(docs['summary'])
print(sorted(docs.get('field_schemas', {})))
"
```

Expected: the v2 summary, with `field_schemas` inherited from v0_5.

- [ ] **Step 4: Document the lookup table resources**

The `id` and `data_type_id` fields on these resources use HQ's `UUIDField`,
whose `'A UUID object'` class default the test correctly rejects. Give them real
descriptions:

```python
    id = UUIDField(
        attribute='id',
        readonly=True,
        help_text='Unique identifier of the lookup table item.',
    )
    data_type_id = UUIDField(
        attribute='table_id',
        help_text='Identifier of the lookup table this item belongs to.',
    )
```

- [ ] **Step 5: Add example files and run the tests**

Create the three example files listed under **Files** above, copying each sample
response from the matching RST page (`locations-v1.rst`, `locations-v2.rst`,
`fixture.rst`). Confirm each parses, then run the tests:

```bash
for f in corehq/apps/api/openapi/examples/location/v1/list_response.json \
         corehq/apps/api/openapi/examples/location/v2/list_response.json \
         corehq/apps/api/openapi/examples/lookup_table/v1/list_response.json; do
  python -c "import json; json.load(open('$f'))" || echo "BAD: $f"
done
uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/ -v
uv run pytest --reusedb=1 corehq/apps/api/tests/lookup_table_resources.py \
  corehq/apps/locations/tests/ -v
```

Expected: openapi tests pass; location and lookup table tests unchanged.

- [ ] **Step 6: Convert the RST pages and regenerate**

```bash
uv run ./manage.py generate_openapi
cd docs && uv run make html && cd ..
```

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff format corehq/apps/locations corehq/apps/fixtures corehq/apps/api
uv run ruff check corehq/apps/locations corehq/apps/fixtures corehq/apps/api
git add corehq/apps docs/api
git commit -m "Document the location and lookup table APIs in code"
```

---

### Task 13: Case API v2

The non-Tastypie path. Query parameters come from the filter dicts in
`corehq/apps/hqcase/api/get_list.py`; request bodies come from the `jsonobject`
classes in `corehq/apps/hqcase/api/updates.py`.

**Files:**

- Create: `corehq/apps/api/openapi/jsonobject_schema.py`
- Create: `corehq/apps/api/openapi/view_adapter.py`
- Create: `corehq/apps/api/openapi/tests/test_jsonobject_schema.py`
- Create: `corehq/apps/api/openapi/tests/test_view_adapter.py`
- Modify: `corehq/apps/hqcase/api/get_list.py` (parameter descriptions)
- Modify: `corehq/apps/hqcase/views.py` (`@api_docs` on `case_api`)
- Modify: `corehq/apps/api/openapi/builder.py` (include view-based entries)
- Create: `corehq/apps/api/openapi/examples/case/v2/*.json`
- Modify: `docs/api/cases-v2.rst`, `docs/api/spec/*.json`

**Interfaces:**

- Consumes: `build_document` (Task 7), `field_to_schema` (Task 4).
- Produces:

  - `jsonobject_to_schema(cls: type) -> dict` — a `jsonobject.JsonObject`
    subclass to a JSON Schema object, with `required` and `enum` from
    `required=` and `choices=`.
  - `api_docs(*, summary, description, paths, examples=None, parameters=None, request_schemas=None) -> Callable`
    — decorator storing an `ApiViewDocs` on the view as `view._openapi_docs`.
  - `VIEW_DOCS: list` — registry of decorated views, in `view_adapter.py`.

- [ ] **Step 1: Write the failing jsonobject test**

```python
from corehq.apps.api.openapi.jsonobject_schema import jsonobject_to_schema
from corehq.apps.hqcase.api.updates import JsonCaseCreation, JsonIndex


def test_string_properties_and_choices():
    schema = jsonobject_to_schema(JsonIndex)
    assert schema['type'] == 'object'
    assert schema['properties']['case_id'] == {'type': 'string'}
    assert schema['properties']['relationship'] == {
        'type': 'string',
        'enum': ['child', 'extension'],
    }


def test_required_properties_are_listed():
    schema = jsonobject_to_schema(JsonCaseCreation)
    assert set(schema['required']) >= {
        'case_name', 'case_type', 'owner_id', 'user_id',
    }


def test_boolean_and_dict_properties():
    schema = jsonobject_to_schema(JsonCaseCreation)
    assert schema['properties']['close'] == {
        'type': 'boolean',
        'default': False,
    }
    assert schema['properties']['properties']['type'] == 'object'


def test_nested_object_properties_recurse():
    schema = jsonobject_to_schema(JsonCaseCreation)
    indices = schema['properties']['indices']
    assert indices['type'] == 'object'
    assert indices['additionalProperties']['properties']['relationship'] == {
        'type': 'string',
        'enum': ['child', 'extension'],
    }
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_jsonobject_schema.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the jsonobject mapping**

```python
"""Mapping from ``jsonobject`` request models to JSON Schema."""
import jsonobject

PROPERTY_TYPES = {
    jsonobject.StringProperty: {'type': 'string'},
    jsonobject.BooleanProperty: {'type': 'boolean'},
    jsonobject.IntegerProperty: {'type': 'integer'},
    jsonobject.FloatProperty: {'type': 'number'},
    jsonobject.DecimalProperty: {'type': 'string', 'format': 'decimal'},
    jsonobject.DateProperty: {'type': 'string', 'format': 'date'},
    jsonobject.DateTimeProperty: {'type': 'string', 'format': 'date-time'},
}


def _property_schema(prop):
    for prop_type, schema in PROPERTY_TYPES.items():
        if isinstance(prop, prop_type):
            schema = dict(schema)
            break
    else:
        schema = None

    if isinstance(prop, jsonobject.DictProperty):
        schema = {'type': 'object'}
        item_wrapper = getattr(prop, 'item_wrapper', None)
        item_type = getattr(item_wrapper, 'item_type', None)
        if item_type is not None and issubclass(
            item_type, jsonobject.JsonObject
        ):
            schema['additionalProperties'] = jsonobject_to_schema(item_type)
        else:
            schema['additionalProperties'] = True
    elif isinstance(prop, jsonobject.ListProperty):
        schema = {'type': 'array', 'items': {}}
    elif isinstance(prop, jsonobject.ObjectProperty):
        return jsonobject_to_schema(prop.item_type)

    if schema is None:
        return {}

    choices = getattr(prop, 'choices', None)
    if choices:
        schema['enum'] = list(choices)

    default = _default_value(prop)
    if default is not None:
        schema['default'] = default
    return schema


def _default_value(prop):
    """The property's default, or ``None`` if it has none.

    ``jsonobject`` wraps every declared default in a zero-argument callable,
    so the value has to be computed rather than read.
    """
    default = getattr(prop, 'default', None)
    if default is None:
        return None
    if callable(default):
        try:
            default = default()
        except Exception:
            return None
    return default if default not in (None, (), {}, []) else None


def jsonobject_to_schema(cls):
    """JSON Schema for a ``jsonobject.JsonObject`` subclass."""
    properties = {}
    required = []
    for key, prop in cls._properties_by_key.items():
        properties[key] = _property_schema(prop)
        if getattr(prop, 'required', False):
            required.append(key)
    schema = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = sorted(required)
    return schema
```

`_properties_by_key` is the right attribute — it is keyed by JSON key, which is
what a request body schema needs. (`_properties_by_name` does not exist;
`_properties_by_attr` is keyed by Python attribute name.) Verified in this
codebase: `JsonCaseCreation._properties_by_key['close'].default()` returns
`False`, `['properties'].default()` returns `{}`, and
`['indices'].item_wrapper.item_type` is `JsonIndex`.

- [ ] **Step 4: Run it to verify it passes**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_jsonobject_schema.py -v`
Expected: 4 passed.

- [ ] **Step 5: Write the failing view adapter test**

```python
from corehq.apps.api.openapi.view_adapter import VIEW_DOCS, api_docs


def test_decorator_registers_docs_and_returns_the_view():
    @api_docs(
        summary='Test endpoint',
        description='A test endpoint.',
        doc_slug='test-v1',
        paths=['/a/{domain}/api/test/v1/'],
    )
    def view(request, domain):
        return 'called'

    assert view(None, 'demo') == 'called'
    assert view._openapi_docs.summary == 'Test endpoint'
    assert view._openapi_docs.paths == ['/a/{domain}/api/test/v1/']
    assert view._openapi_docs in VIEW_DOCS


def test_case_api_is_documented():
    from corehq.apps.hqcase.views import case_api

    docs = case_api._openapi_docs
    assert docs.summary
    assert '/a/{domain}/api/case/v2/' in docs.paths
    assert 'case_type' in {p['name'] for p in docs.parameters}


def test_case_api_declares_request_schemas():
    from corehq.apps.hqcase.views import case_api

    schemas = case_api._openapi_docs.request_schemas
    assert 'post' in schemas
    assert schemas['post']['type'] in ('object', 'array')
```

- [ ] **Step 6: Run it to verify it fails**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_view_adapter.py -v`
Expected: FAIL — module not found.

- [ ] **Step 7: Implement the decorator**

```python
"""Documentation declarations for function-based API views.

Tastypie resources declare documentation through a ``Docs`` inner class. The
hand-written API views use this decorator instead, which carries the same
information plus the paths the view serves.
"""
import functools
from dataclasses import dataclass, field

VIEW_DOCS = []


@dataclass
class ApiViewDocs:
    summary: str
    description: str
    paths: list
    doc_slug: str
    methods: list = field(default_factory=lambda: ['get'])
    parameters: list = field(default_factory=list)
    request_schemas: dict = field(default_factory=dict)
    response_schemas: dict = field(default_factory=dict)
    examples: dict = field(default_factory=dict)


def api_docs(**kwargs):
    """Attach OpenAPI documentation to a function-based API view."""
    docs = ApiViewDocs(**kwargs)

    def decorate(view):
        VIEW_DOCS.append(docs)

        @functools.wraps(view)
        def wrapper(*args, **view_kwargs):
            return view(*args, **view_kwargs)

        wrapper._openapi_docs = docs
        return wrapper

    return decorate
```

- [ ] **Step 8: Describe the Case API v2 filters**

In `corehq/apps/hqcase/api/get_list.py`, add a descriptions mapping next to the
filter dicts so the parameters and the filters that implement them stay
together:

```python
# Descriptions for the query parameters generated from the filters above.
FILTER_DESCRIPTIONS = {
    'external_id': 'Return cases with this external ID.',
    'case_type': 'Return cases of this case type.',
    'owner_id': 'Return cases owned by this user or group ID.',
    'case_name': 'Return cases with this case name.',
    'closed': 'Return only closed (true) or only open (false) cases.',
    INCLUDE_DEPRECATED: 'Include cases whose case type is deprecated.',
    'properties': 'Filter by case property, as properties.<name>=<value>.',
    'last_modified': 'Filter by modification date, as '
                     'last_modified.gte=<date>.',
    'server_last_modified': 'Filter by server modification date.',
    'date_opened': 'Filter by the date the case was opened.',
    'date_closed': 'Filter by the date the case was closed.',
    'indexed_on': 'Filter by the date the case was indexed for search.',
    'indices': 'Return cases indexed by the given case, as '
               'indices.<identifier>=<case_id>.',
}


def filter_parameters():
    """OpenAPI query parameters for the filters this module implements."""
    parameters = []
    for name in sorted({*SIMPLE_FILTERS, *COMPOUND_FILTERS}):
        parameters.append({
            'name': name,
            'in': 'query',
            'required': False,
            'description': FILTER_DESCRIPTIONS[name],
            'schema': {'type': 'string'},
        })
    return parameters
```

Add a test in `corehq/apps/api/openapi/tests/test_view_adapter.py` that every
filter has a description, so adding a filter without documenting it fails:

```python
def test_every_case_api_filter_has_a_description():
    from corehq.apps.hqcase.api.get_list import (
        COMPOUND_FILTERS,
        FILTER_DESCRIPTIONS,
        SIMPLE_FILTERS,
    )

    filters = {*SIMPLE_FILTERS, *COMPOUND_FILTERS}
    assert filters <= set(FILTER_DESCRIPTIONS), (
        'undocumented Case API filters: '
        f'{sorted(filters - set(FILTER_DESCRIPTIONS))}'
    )
```

- [ ] **Step 9: Decorate the case API view**

In `corehq/apps/hqcase/views.py`, decorate `case_api`. Place `@api_docs`
outermost so it does not interfere with the auth and CSRF decorators.

```python
@api_docs(
    summary='Cases',
    description=(
        'Fetch, create and update cases. GET returns a page of cases '
        'matching the given filters, or a single case when a case ID is '
        'given. POST creates or updates cases; a single object creates or '
        'updates one case, and a list performs a bulk change.'
    ),
    doc_slug='case-v2',
    paths=['/a/{domain}/api/case/v2/', '/a/{domain}/api/case/v2/{case_id}/'],
    methods=['get', 'post', 'put'],
    parameters=filter_parameters(),
    request_schemas={'post': jsonobject_to_schema(JsonCaseCreation)},
    examples={'post_request': 'case/v2/post_request.json'},
)
def case_api(request, domain, case_id=None):
    ...
```

Import `filter_parameters` from `corehq.apps.hqcase.api.get_list`,
`jsonobject_to_schema` from `corehq.apps.api.openapi.jsonobject_schema`,
`JsonCaseCreation` from `corehq.apps.hqcase.api.updates`, and `api_docs` from
`corehq.apps.api.openapi.view_adapter`.

- [ ] **Step 10: Include view docs in the built documents**

In `builder.py`, add a function that turns an `ApiViewDocs` into path items, and
include those docs in `build_all`:

```python
def view_paths(docs):
    """OpenAPI path items for a documented function-based view."""
    from corehq.apps.api.openapi.operations import (
        DOMAIN_PARAMETER,
        load_example,
    )

    paths = {}
    for path in docs.paths:
        item = {'parameters': [DOMAIN_PARAMETER]}
        is_detail = path.rstrip('/').endswith('}')
        for method in docs.methods:
            operation = {
                'summary': docs.summary,
                'description': docs.description,
                'operationId': (
                    f'{docs.doc_slug}_{"detail" if is_detail else "list"}'
                    f'_{method}'
                ),
                'tags': [docs.doc_slug],
                'responses': {
                    '200': {'description': 'Success.'},
                },
            }
            if method == 'get' and not is_detail:
                operation['parameters'] = docs.parameters
            schema = docs.request_schemas.get(method)
            if schema:
                body = {'schema': schema}
                example = docs.examples.get(f'{method}_request')
                if example:
                    body['example'] = load_example(example)
                operation['requestBody'] = {
                    'required': True,
                    'content': {'application/json': body},
                }
            item[method] = operation
        paths[path] = item
    return paths
```

Then in `build_all`, after building the resource documents, add one document per
view slug and merge the view paths into the bundle:

```python
def build_all():
    entries = documented_entries()
    documents = {
        entry.doc_slug: build_document([entry], title=_title(entry))
        for entry in entries
    }
    bundle = build_document(entries, title='CommCare Data APIs')

    from corehq.apps.hqcase import views  # noqa: F401  (registers view docs)
    from corehq.apps.api.openapi.view_adapter import VIEW_DOCS

    for docs in VIEW_DOCS:
        paths = view_paths(docs)
        document = build_document([], title=docs.summary)
        document['paths'] = paths
        documents[docs.doc_slug] = document
        bundle['paths'].update(paths)

    documents['bundle'] = bundle
    return documents
```

Add to `corehq/apps/api/openapi/tests/test_builder.py`:

```python
def test_case_api_v2_is_in_the_generated_documents():
    documents = build_all()
    assert 'case-v2' in documents
    validate(documents['case-v2'])
    paths = documents['case-v2']['paths']
    assert '/a/{domain}/api/case/v2/' in paths
    assert 'requestBody' in paths['/a/{domain}/api/case/v2/']['post']
```

- [ ] **Step 11: Add the request example, regenerate, and convert the page**

Create `corehq/apps/api/openapi/examples/case/v2/post_request.json` from the
sample in `docs/api/cases-v2.rst`, then:

```bash
uv run ./manage.py generate_openapi
uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/ -v
uv run pytest --reusedb=1 corehq/apps/hqcase/tests/ -v
```

Expected: all pass. The `hqcase` tests confirm the decorator did not change the
view's behaviour.

Convert `docs/api/cases-v2.rst` to a directive over `spec/case-v2.json`
following the Task 10 pattern, then rebuild the docs.

- [ ] **Step 12: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi corehq/apps/hqcase
uv run ruff check corehq/apps/api/openapi corehq/apps/hqcase
git add corehq/apps docs/api
git commit -m "Generate an OpenAPI spec for Case API v2

Query parameters generate from the filter dicts that implement them, and
request bodies from the jsonobject request models, so both fail loudly when a
filter or property is added without documentation."
```

---

### Task 14: Contract validation against real responses

Verifies the specs describe what the APIs actually return, rather than trusting
the generator.

**Files:**

- Modify: `pyproject.toml` (add `openapi-core` to the `test` group)
- Create: `corehq/apps/api/openapi/tests/test_contract.py`

**Interfaces:**

- Consumes: `build_all` (Task 7), `APIResourceTest` from
  `corehq/apps/api/tests/utils.py`.
- Produces: nothing.

`APIResourceTest` (in `corehq/apps/api/tests/utils.py`) sets up a domain, a web
user, an `HQApiKey`, and a billing subscription, and exposes helpers for calling
the API. Subclass it so the contract test exercises the real request path.

- [ ] **Step 1: Write the failing test**

```python
import json

from openapi_core import OpenAPI
from openapi_core.contrib.django import DjangoOpenAPIRequest

from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.resources import v0_5
from corehq.apps.api.tests.utils import APIResourceTest
from corehq.apps.users.models import CommCareUser


class TestUserApiMatchesItsSpec(APIResourceTest):
    resource = v0_5.CommCareUserResource
    api_name = 'v1'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.commcare_user = CommCareUser.create(
            domain=cls.domain.name,
            username='listed@{}.commcarehq.org'.format(cls.domain.name),
            password='**********',
            created_by=None,
            created_via=None,
            first_name='Listed',
            last_name='User',
        )
        cls.addClassCleanup(cls.commcare_user.delete, cls.domain.name, None)

    def test_list_response_conforms_to_the_spec(self):
        spec = OpenAPI.from_dict(build_all()['user-v1'])
        response = self._assert_auth_get_resource(self.list_endpoint)
        assert response.status_code == 200, response.content

        payload = json.loads(response.content)
        schema = (
            spec.spec.contents()['paths']['/a/{domain}/api/user/v1/']['get']
            ['responses']['200']['content']['application/json']['schema']
        )
        properties = schema['properties']['objects']['items']['properties']
        spec_fields = set(properties)
        response_fields = set(payload['objects'][0])
        assert response_fields <= spec_fields, (
            'response fields missing from the spec: '
            f'{sorted(response_fields - spec_fields)}'
        )
        assert set(payload['meta']) <= {
            'limit', 'offset', 'total_count', 'next', 'previous',
        }
```

- [ ] **Step 2: Add the dependency**

Add `'openapi-core'` to the `test` list in `[dependency-groups]` in
`pyproject.toml`, then `uv sync --compile-bytecode`.

- [ ] **Step 3: Run the test**

Run:
`uv run pytest --reusedb=1 corehq/apps/api/openapi/tests/test_contract.py -v`
Expected: PASS, or FAIL naming response fields absent from the spec. A failure
here is a real finding — a field the API returns that the generator did not
describe. Fix the generator or add the missing field's documentation; do not
relax the assertion.

If `_assert_auth_get_resource` or `list_endpoint` are named differently on
`APIResourceTest`, read `corehq/apps/api/tests/utils.py` and use the actual
helpers rather than inventing a request.

- [ ] **Step 4: Lint and commit**

```bash
uv run ruff format corehq/apps/api/openapi
uv run ruff check corehq/apps/api/openapi
git add corehq/apps/api/openapi pyproject.toml uv.lock
git commit -m "Validate API responses against their OpenAPI spec"
```

---

### Task 15: Wire the drift checks into CI, and document the workflow

**Files:**

- Modify: `docs/api/index.rst` (note the specs and how to regenerate)
- Create: `corehq/apps/api/openapi/README.md`

**Interfaces:**

- Consumes: everything.
- Produces: nothing.

The no-drift and undocumented-field checks are pytest tests (Tasks 8, 9), so
they already run in CI with the rest of the suite — no CI config change is
needed. This task documents the workflow for the next person.

- [ ] **Step 1: Write the package README**

Create `corehq/apps/api/openapi/README.md`:

```markdown
# OpenAPI specs for the CommCare data APIs

The specs under `docs/api/spec/` are generated from the API code and committed,
so a change to an API's shape appears as a reviewable diff.

## Regenerating

    ./manage.py generate_openapi

`./manage.py generate_openapi --check` fails if the committed specs are stale.
The same check runs as a test
(`corehq/apps/api/openapi/tests/test_generate_openapi.py`).

## Adding documentation for an API

1. Add the resource version to `catalogue.py` with a `doc_slug`.
2. Give every field a real `help_text`. A field that still carries its field
   type's class default counts as undocumented and fails
   `tests/test_documented_fields.py`.
3. Add a `Docs` inner class with `summary`, `description`, and optionally
   `examples` and `field_schemas`. `Docs` is merged across the class hierarchy,
   so put shared documentation on the base resource and override only what
   changes in a later version.
4. Put JSON examples under `examples/<resource>/<version>/` and reference them
   by relative path.
5. Add the slug to `DOCUMENTED_SLUGS` in `tests/test_documented_fields.py`.
6. Regenerate, and point the `docs/api/*.rst` page at the new spec with the
   `openapi::` directive.

Function-based views use the `@api_docs` decorator in `view_adapter.py` instead
of a `Docs` class.

## Known limitation

Tastypie's own `.../schema/` endpoints return HTTP 500 for resources that are
not `ModelResource` subclasses, because `get_schema()` calls
`get_object_list()`. That is a pre-existing bug and unrelated to this generator,
which calls `build_schema()` in-process. See the design doc.
```

- [ ] **Step 2: Note the specs in the docs index**

Add to `docs/api/index.rst`, after the intro paragraph:

```rst
Machine-readable specifications
-------------------------------

These pages are generated from OpenAPI 3.0.3 specifications under
``docs/api/spec/``. ``bundle.json`` covers every documented endpoint and is
intended for code generation and for tools that consume the whole API
surface.
```

- [ ] **Step 3: Add a Spectral lint pass**

The spec calls for Spectral lint alongside schema validation, to catch style
problems the validator accepts — missing descriptions, missing `operationId`,
and so on. Create `docs/api/spec/.spectral.yaml`:

```yaml
extends: ["spectral:oas"]
rules:
  # The bundle intentionally has no top-level tags declaration.
  openapi-tags: off
  # Contact and licence live on the docs site, not in each spec.
  info-contact: off
  info-license: off
  license-url: off
```

Run it and fix anything it reports:

```bash
npx --yes @stoplight/spectral-cli lint \
  --ruleset docs/api/spec/.spectral.yaml \
  docs/api/spec/*.json
```

Expected: no errors. Warnings are acceptable if you have read them and they are
consistent with the design (for example, operation-level `description`
duplication across a resource's methods). Record the command in the README from
Step 1 so the next person can run it.

- [ ] **Step 4: Run the whole API test suite**

```bash
uv run pytest --reusedb=1 corehq/apps/api corehq/apps/hqcase -v
```

Expected: all pass. This is the last gate before handing the branch over.

- [ ] **Step 5: Build the docs one final time**

```bash
cd docs && uv run make html && cd ..
```

Expected: no warnings referring to `spec/` or the `openapi` directive.

- [ ] **Step 6: Commit**

```bash
npx prettier --write corehq/apps/api/openapi/README.md
git add corehq/apps/api/openapi/README.md docs/api/index.rst
git commit -m "Document the OpenAPI generation workflow"
```

---

## Verification checklist

Before considering the branch complete:

- [ ] `uv run pytest --reusedb=1 corehq/apps/api corehq/apps/hqcase` passes
- [ ] `uv run ./manage.py generate_openapi --check` reports up to date
- [ ] `cd docs && uv run make html` builds without spec-related warnings
- [ ] Every generated document under `docs/api/spec/` passes
      `openapi-spec-validator` (covered by `test_builder.py`)
- [ ] `npx --yes @stoplight/spectral-cli lint --ruleset     docs/api/spec/.spectral.yaml docs/api/spec/*.json`
      reports no errors
- [ ] `git diff master --stat` shows no changes to `_OLD_API_LIST`,
      `versioned_apis()` or `ADMIN_API_LIST` in `corehq/apps/api/urls.py`
