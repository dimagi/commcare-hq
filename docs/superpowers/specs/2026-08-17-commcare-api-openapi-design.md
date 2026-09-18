# OpenAPI specs for the CommCare data APIs

Date: 2026-08-17

## Purpose

Produce OpenAPI specifications for the CommCare data APIs, and make those specs
the source of truth for the public API documentation.

Target version is **OpenAPI 3.0.3**. `sphinxcontrib-openapi`'s documentation
does not state whether it handles 3.1, and its own examples are Swagger 2.0, so
3.1 is deferred until the renderer is confirmed to support it. Confirming the
version the renderer actually accepts is the first task of step 2 in the
sequencing below; if 3.0.3 proves troublesome, the fallback is
`sphinxcontrib-redoc` over the same generated bundle, which changes only the
rendering decision and none of the generation design.

Consumers, in priority order:

1. **Public documentation** for humans, replacing the hand-maintained
   per-endpoint pages under `docs/api/`.
2. **Agents** reading the same documentation, which raises the bar on
   descriptions: prose must be accurate and self-contained, not a pointer to a
   Confluence page.
3. **Task-based MCP services** built over the APIs. These need reliable
   parameter and response shapes, but not a rigorously typed contract.

Non-goals: generating client SDKs, specifying the legacy `v0.x` URLs, and
documenting the admin and accounting resources publicly.

## Current state

### Tastypie resources

`django-tastypie` 0.15.1. `corehq/apps/api/urls.py` routes roughly 30
domain-scoped resources at current versions, plus 2 user-scoped and about 25
admin and accounting resources. Resource classes live in
`corehq/apps/api/resources/v0_1.py` through `v1_0.py`, and in the `locations`,
`fixtures`, `commtrack`, `enterprise` and `zapier` apps.

All legacy `v0.5` URLs are duplicated as `v1` and all `v0.6` URLs as `v2`, per
the module docstring in `urls.py`.

Every resource already carries a machine-readable description via
`Resource.build_schema()`. It reports, per field, the `dehydrated_type`,
`nullable`, `blank`, `readonly`, `unique`, `default` and `help_text`; and per
resource, `allowed_list_http_methods`, `allowed_detail_http_methods`,
`default_limit`, `ordering` and `filtering`.

Verified against all 33 documented resources at their current versions: every
one builds a schema successfully when called in-process, with no failures.

**The `.../schema/` endpoints, however, are broken for 28 of those 33.**
Tastypie's `get_schema()` view does not merely call `build_schema()`; it first
calls `self.authorized_read_detail(self.get_object_list(request), bundle)`, and
`Resource.get_object_list` raises `NotImplementedError`. Only resources that
supply one — the four `ModelResource` subclasses (`DeviceReportResource`, both
`LocationResource` versions, `LocationTypeResource`) plus `UserDomainsResource`
— return a schema. The other 28 return HTTP 500. Confirmed against a dev server:
`/a/demo/api/location_type/v1/schema/` returns 200,
`/a/demo/api/group/v1/schema/` returns 500.

This does not affect the design below, because the generator calls
`build_schema()` in-process rather than over HTTP, and that path is sound for
every resource. It does mean the existing `.../schema/` endpoints cannot be
treated as a working feature — see "Pre-existing schema endpoints" under Open
questions.

Three gaps limit what introspection alone can produce:

- Effectively no resource sets a real `help_text`, so fields report their field
  type's generic class default, such as
  `'Unicode string data. Ex: "Hello World"'`. Seven fields across the fixtures
  and lookup-table resources report `'A UUID object'`, but that too is a class
  default — of HQ's own `UUIDField` in `corehq/apps/api/fields.py` — not a
  field-specific description. The undocumented-field check must therefore treat
  HQ's custom field class defaults as generic alongside Tastypie's.
- `ListField` and `DictField` carry no item schema, so fields like
  `phone_numbers`, `user_data` and case `properties` introspect as untyped
  containers.
- Only four resources declare `Meta.filtering`, so most documented query
  parameters have to be declared rather than derived.

### APIs that are not Tastypie

Roughly eight surfaces are plain Django views: Case API v2
(`corehq/apps/hqcase/views.py` with `corehq/apps/hqcase/api/`), messaging-event,
the OData case and form feeds, UCR data, generic inbound, case and form
attachments, OpenRosa form submission, and OTA restore.

Case API v2 is the most significant of these. Its query parameters come from
module-level `SIMPLE_FILTERS` and `COMPOUND_FILTERS` dicts in
`corehq/apps/hqcase/api/get_list.py`, and its request bodies from `jsonobject`
classes in `corehq/apps/hqcase/api/updates.py`.

### Documentation

`docs/api/` holds 27 hand-written reStructuredText pages, each with a purpose
statement, base URL, permissions, input parameter table, output field table, and
JSON examples. They publish to `commcare-hq.readthedocs.io`. `docs/conf.py`
already boots Django via `init_hq_python_path()` and `sphinxcontrib_django`, so
a Sphinx extension can call into HQ code at docs-build time.

There is no OpenAPI anywhere in the repository.

### Existing tooling considered and rejected

`django-tastypie-openapi` is the only off-the-shelf option. It is alpha, has one
GitHub star, and emits only six fixed operation shapes. Its approach of walking
the `Api` object is right, and is a small amount of code to own directly.
`drf-spectacular` does not apply: `djangorestframework` is a dependency, but
only its serializers are used, in three modules unrelated to these APIs.

## Decisions

Each of these was chosen over the stated alternatives.

**The spec is the source of truth; the RST pages are generated from it.**
Rejected: keeping the RST pages hand-maintained alongside a new spec artifact,
which leaves two descriptions of every endpoint to keep in sync; and parsing the
RST tables to feed the spec, which is brittle and maps poorly onto per-field
JSON Schema.

**Documentation content lives in code, not in overlay files.** Field
descriptions use Tastypie's existing `help_text` field argument, which
`build_schema()` already surfaces. The decisive reason is inheritance: the
resource classes are layered — `v0_6.LocationResource` extends
`v0_5.LocationResource`, `v0_6.LookupTableItemResource` extends
`v0_1.LookupTableItemResource`, `v0_5.CommCareUserResource` extends
`v0_1.CommCareUserResource` extends `UserResource`, and
`v0_4.CommCareCaseResource` extends `v0_3.CommCareCaseResource`. A description
attached to a field inherits with that field. An overlay file keyed by resource
and version would either duplicate shared descriptions across versions or have
to reimplement inheritance.

A second benefit: because each field type's `help_text` class default is a known
generic string, "still the class default" is a precise signal for
"undocumented", which CI can enforce with no separate bookkeeping.

The cost accepted: documentation edits become Python changes spread across
several apps, and go through code review.

**Endpoint-level narrative also lives in code**, in a `Docs` inner class that
inherits alongside the fields. Large JSON examples are held in files and
referenced by path, so payloads stay out of Python. Rejected: capturing examples
from test fixtures, which cannot go stale but requires a capture harness and
tends to yield minimal, unrealistic payloads; and per-endpoint Markdown files,
which split authoring across two places and reintroduce the per-version
duplication problem.

**Published docs render via `sphinxcontrib-openapi`.** Each `docs/api/*.rst`
becomes a title plus an `openapi::` directive, and the extension renders into
the existing RTD theme. Rejected: owning a renderer that reproduces today's page
layout exactly, which preserves the current appearance at the cost of a few
hundred lines we maintain forever; and `sphinxcontrib-redoc`, which gives a
better browsing experience for integrators but sits apart from the rest of the
HQ docs and loses the per-API toctree. ReDoc remains available later as an
additional rendering of the same bundle.

Accepted consequence: published pages will be endpoint-first rather than
prose-first, and per-page details such as "Permissions Required" move into
generated description text.

**Artifacts are committed, with a CI no-drift check.** One spec file per API
plus a merged bundle, both committed, so a change to a resource's shape appears
as a reviewable diff in the pull request that causes it. Rejected: a live
`/api/openapi.json` endpoint, which avoids any staleness window and gives
integrators a stable URL, but adds a public view, a cache strategy, and
questions about whether the spec varies by plan or feature flag. This can be
added later over the same builder; it is deferred, not ruled out.

## Architecture

New package `corehq/apps/api/openapi/`:

    catalogue.py          the routed-and-documented API registry
    docs.py               collects in-code documentation: Docs, help_text
    schema.py             Tastypie field metadata -> JSON Schema
    operations.py         Tastypie resource -> paths, operations, parameters
    security.py           securitySchemes and required-permission text
    view_adapter.py       @api_docs decorator for function-based views
    jsonobject_schema.py  jsonobject class -> JSON Schema
    builder.py            document assembly: components, paths, security
    examples/             JSON example payloads referenced by Docs
    management/commands/generate_openapi.py

The Tastypie side is split across `docs.py`, `schema.py`, `operations.py` and
`security.py` rather than gathered into one adapter module, so that each piece
is a small pure function testable on its own: field-type mapping, filter-to-
parameter, authentication-to-permission, and documentation collection are
independent concerns with independent tables of cases.

### The catalogue

A single list of entries, each pairing a resource class with a version and,
where the API is public, a documentation slug:

```python
@dataclass(frozen=True)
class ApiEntry:
    resource: type
    version: str
    doc_slug: str | None = None   # None: routed but not publicly documented
```

`urls.py` builds its URL patterns from this list rather than from the current
flat sequence of `Resource.get_urlpattern('v1')` calls, and the spec builder
reads the same list, filtered to entries with a `doc_slug`. A resource therefore
cannot be routed without appearing in the catalogue, and the spec cannot
describe an endpoint that is not routed. Drift is prevented by construction
rather than by a CI check.

`doc_slug` names the **generated spec document**, not a documentation page. The
RST pages are not one-to-one with resources — `form-data.rst` and
`list-forms.rst` both describe `XFormInstanceResource`, and `mobile-worker.rst`
and `list-mobile-workers.rst` both describe `CommCareUserResource` — so a page
selects what it renders from a spec using the `openapi::` directive's `:paths:`
or `:include:` option. Slugs are therefore named after the resource and version,
such as `user-v1`.

Scope of the refactor:

- The flat list of `get_urlpattern` calls in `urlpatterns` is replaced by a
  comprehension over the catalogue. **URL pattern order must be preserved**,
  since Django resolves in order; the catalogue is ordered to match the current
  sequence, and a test asserts the resolved pattern list is unchanged.
- The catalogue covers only the resources routed through `get_urlpattern()` —
  the domain-scoped and user-scoped ones. Undocumented resources among them are
  entered with `doc_slug=None`, so routing has a single source while the public
  spec filters them out.
- **Admin and accounting resources stay outside the catalogue.**
  `ADMIN_API_LIST` is registered through a different mechanism —
  `CommCareHqApi(api_name='global')` with `api.register()`, not
  `get_urlpattern()` — so bringing it in would mean refactoring a second routing
  path for resources that are an explicit non-goal of this work.
  `ADMIN_API_LIST` is left exactly as it is.
- `_OLD_API_LIST` — the legacy `v0.3` through `v0.6` URLs registered through
  `versioned_apis()` — is left exactly as it is. Those URLs are deprecated
  duplicates and are out of scope for documentation.
- `ApiVersioningMixin.__init__` exists because Tastypie's `_meta` is a singleton
  shared across a resource class, so `api_name` bleeds between registrations.
  The generator must instantiate one resource per catalogue entry, exactly as
  the URL code does, rather than reusing an instance across versions.

This is the only change to existing behaviour in the design; everything else is
additive.

### Tastypie adapter

Drives off `build_schema()`:

- `dehydrated_type` maps to JSON Schema: `string`, `integer`, `float`,
  `decimal`, `boolean`, `list`, `dict`, `date`, `datetime`, `time`, `related`.
  Dates and datetimes carry the corresponding `format`.
- `list_allowed_methods` and `detail_allowed_methods` become the operations on
  the list and detail paths. Several documented resources allow writes — for
  example `CommCareUserResource` v1 allows `POST` on the list and `PUT` and
  `DELETE` on the detail endpoint — so this is not a read-only surface.
- `Meta.filtering` entries plus the standard `limit`, `offset`, `format` and
  `order_by` parameters become query parameters. `exact` yields a bare `field`
  parameter; any other filter name yields `field__<filter>`; the `ALL` and
  `ALL_WITH_RELATIONS` constants are treated as `exact`.
- `nullable`, `readonly` and `default` become field constraints.
- **Write operations carry a `requestBody`** whose schema is the resource's
  fields with the read-only ones removed. `POST` on the list path and `PUT` or
  `PATCH` on the detail path get one; `GET` and `DELETE` do not.
- `Meta.ordering` enumerates the permitted `order_by` values.

Two pieces of prose currently hand-written in the RST pages are derived instead
of transcribed:

- `RequirePermissionAuthentication` retains its `HqPermissions` argument as
  `self.permission`, so the required permission is read from the resource's
  authentication class. An `HqPermissions` member is a
  `jsonobject.BooleanProperty` whose `.name` is the permission name, for example
  `edit_commcare_users`.
- `api_auth` accepts Basic, Digest, session, ApiKey
  (`Authorization: ApiKey <username>:<api_key>`), and OAuth2 with the
  `access_apis` scope. These become one shared `securitySchemes` block,
  replacing the per-page link to the Confluence authentication page.

### The docs contract

Field level, on the field itself:

```python
username = fields.CharField(
    attribute='username',
    unique=True,
    help_text="The user's username, including the domain suffix.",
)
```

Endpoint level, as an inner class that inherits with the resource. Untyped
containers get their item schema here too, in `field_schemas`, since
introspection cannot recover one:

```python
class CommCareUserResource(UserResource):

    class Docs:
        summary = "Mobile Workers"
        description = """..."""
        examples = {'list_response': 'user/v1/list_response.json'}
        field_schemas = {
            'phone_numbers': {
                'items': {'type': 'string'},
                'description': "All phone numbers registered for the user.",
            },
        }
```

`field_schemas` entries are merged over whatever the field introspects to, so a
hand-written schema always wins.

Item schemas live in `Docs` rather than in a `schema=` field argument
deliberately. A field argument would mean new HQ field classes and an edit to
every container field's declaration, which risks changing serialization
behaviour for no benefit; `Docs` needs neither, and is collected by the same
merge as the rest of the documentation.

**`Docs` inheritance is explicit, not implicit.** An inner class is found by
ordinary attribute lookup, so `resource_cls.Docs` on a subclass that declares
its own `Docs` would silently hide the parent's. The collector therefore walks
`resource_cls.__mro__` and reads `klass.__dict__['Docs']` per class, base first,
so subclass values override and dict values such as `examples` and
`field_schemas` are shallow-merged.

Function-based views declare the same structure through a decorator, plus the
paths they serve, which a resource supplies from its `Meta` but a view cannot:

```python
@api_docs(
    summary="Cases",
    description="...",
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

### Case API v2

This is the proving ground for the non-Tastypie path, and is included in the
first slice for that reason and because it is heavily used.

- Query parameters generate from `SIMPLE_FILTERS` and `COMPOUND_FILTERS`. Both
  are enumerable dicts; descriptions are supplied alongside the dict entries so
  the parameter list cannot silently diverge from the filters actually
  implemented.
- Request bodies generate from the `jsonobject` classes in `updates.py`.
  `StringProperty` and friends map to types, and `choices=` maps to `enum` — for
  example `JsonIndex.relationship`, whose choices are `child` and `extension`.
- Where introspection is not clean enough, `api_docs` accepts a literal schema
  for that request or response.

### Path templating

Domain-scoped APIs are described as `/a/{domain}/api/{resource}/{version}/`,
with `domain` as a path parameter. User-scoped APIs use their own prefix. The
server URL is declared with the CommCare HQ instance as a variable, so specs are
usable against non-production deployments.

## Outputs

`./manage.py generate_openapi` writes, under `docs/api/spec/`:

- one document per documented API, named by `doc_slug`
- a merged bundle covering the whole documented surface

All are committed. Sphinx renders the per-API documents; machine consumers read
the bundle.

The `openapi::` directive needs `:examples:` passed for request and response
examples to render at all — without it they are omitted, and where a spec
supplies none the extension invents them from the schema, which we do not want
in published docs. The directive can also filter a single spec by `:paths:`,
`:include:` or `:exclude:`, so per-API documents are a convenience for
reviewable diffs rather than a requirement of the renderer.

## Testing

Following the repository's preference for narrow tests against the helper that
owns the logic:

- Unit tests on each adapter: type mapping over the full range of
  `dehydrated_type` values, filtering to parameters, authentication class to
  required-permission text, `jsonobject` property to schema. Parametrized, since
  these are tables of input and expected output.
- `openapi-spec-validator` over every generated document, plus a Spectral lint
  step.
- A no-drift test: regenerate and assert the committed artifacts are unchanged.
  This fails when a resource changes shape without its documentation being
  updated.
- An undocumented-field test: every field of every documented resource must have
  `help_text` other than its field type's class default. The set of generic
  defaults is collected from both Tastypie's field classes and HQ's own in
  `corehq/apps/api/fields.py`, so that a class default like `'A UUID object'` is
  not mistaken for a description.
- A `build_schema()` smoke test over the whole catalogue, asserting every
  documented resource builds a schema. This is currently true for all 33 and is
  a precondition of the generator, so it should fail loudly if a new resource
  breaks it.
- A URL-stability test for the `urls.py` refactor, asserting the resolved
  pattern list is identical before and after.
- Contract validation with `openapi-core`, checking responses captured in the
  existing API tests against the generated schemas, so the spec is verified
  against real serializer output rather than trusted.

## Sequencing

1. Catalogue, `urls.py` refactor, and the URL-stability test.
2. Tastypie adapter, builder, and `user/v1` end to end: spec, generated RST
   page, no-drift and undocumented-field checks in CI.
3. The remaining documented read APIs: cases v1, list-forms, groups, locations
   v1 and v2, lookup tables.
4. Case API v2: `view_adapter`, `jsonobject_schema`, and the filter-dict
   parameter generation.
5. Contract validation wired into the existing API tests.

Steps 1 and 2 establish every mechanism the rest depends on. Step 4 is the one
that proves the design extends to the remaining non-Tastypie surfaces —
messaging-event, OData, UCR, generic inbound, attachments, form submission and
OTA restore — which are out of scope here and follow the same pattern.

## Open questions

### Pre-existing schema endpoints

28 of the 33 documented resources return HTTP 500 from their `.../schema/`
endpoint, as described under Current state. This is a pre-existing bug, not one
this work introduces, and the generator does not depend on those endpoints.
Three ways to treat it:

1. **Out of scope.** Leave them, note the bug, file it separately. Keeps this
   work focused; leaves a documented endpoint that mostly 500s.
2. **Fix.** Implement or override `get_object_list` (or override `get_schema` to
   skip the object-list authorization check) on the affected base classes. Small
   change, but it touches request handling on 28 live resources and needs care
   over what authorization check is being skipped.
3. **Remove.** Once OpenAPI specs are published, per-resource `/schema/` is
   redundant. Removing the route is a breaking change in principle, though for
   28 of 33 resources it currently only breaks a 500.

Recommendation: option 1 for this work, with the bug filed, and a decision on
fix-versus-remove taken separately once the specs are published and it is clear
whether anything still wants the endpoint.
