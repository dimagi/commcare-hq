# OpenAPI 3.0 Spec for CommCare HQ Public APIs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a validated, drift-guarded OpenAPI 3.0 document covering the 25 public APIs documented under `docs/api/`, published as a Redoc page in readthedocs and consumable as LLM tool definitions.

**Architecture:** Multi-file YAML under `docs/api/openapi/` with `$ref`-linked path and component files, bundled by `@redocly/cli` into committed `dist/` artifacts. Content is translated from the reST docs then cross-checked against the tastypie resources that serve each endpoint; disagreements are recorded for human triage, never silently resolved. A pytest module asserts every spec path resolves against Django's URL resolver, so a renamed endpoint fails CI.

**Tech Stack:** OpenAPI 3.0.3, YAML, `@redocly/cli` (Node devDependency), pytest, Sphinx.

**Spec:** `docs/superpowers/specs/2026-08-17-openapi-api-docs-design.md`

## Global Constraints

- **OpenAPI version:** `3.0.3` exactly. Not 3.1 — Redoc's 3.1 support lags, and tool-definition converters are more reliable on 3.0.
- **Spec root:** `docs/api/openapi/openapi.yaml`. Committed artifacts: `docs/api/openapi/dist/openapi.bundled.yaml` and `docs/api/openapi/dist/index.html`.
- **Tags:** exactly four, matching `docs/api/index.rst` categories — `Data`, `Users`, `Submission`, `SMS`.
- **`operationId` convention:** lowerCamelCase verb + resource, e.g. `listCases`, `getCase`, `createMobileWorker`, `updateLocation`. Unique across the document.
- **Every operation MUST have:** `operationId`, `summary` (one line, imperative), `tags`, and at least one response.
- **Every path parameter MUST have an `example`.** This is not cosmetic — the URL-resolution test in Task 4 builds concrete URLs from these examples. A path parameter without an example fails that test.
- **Security schemes:** `ApiKey`, `Basic`, `OAuth2`. Digest and the formplayer HMAC scheme are internal to CommCare mobile and are excluded.
- **Excluded from scope:** `docs/api/ota-api-restore.rst` (opaque app-specific CaseXML), and every resource in `ADMIN_API_LIST` / `_get_global_api_url_patterns` (internal, undocumented).
- **Discrepancy handling:** when a reST doc and the serving code disagree, the spec records **what the code does**, and the disagreement is appended to `docs/superpowers/specs/2026-08-17-openapi-discrepancies.md`. Never "fix" the reST doc as part of this work.
- **YAML style:** 2-space indent, no tabs. Run `npx prettier --write` on YAML files before committing.
- **Branch:** all work on `ce/openapi-spec`. Commit after every task.

## Reference: endpoint inventory

Every path below is confirmed against `corehq/apps/api/urls.py` and the resource classes. Mount points: `urls.py:110` mounts `domain_specific` at `^a/(?P<domain>...)/`, which includes `^api/` at `urls.py:55`; `urls.py:108` mounts `user_urlpatterns` at root `^api/` (so `identity` and `user_domains` have **no** `{domain}` segment).

| Path | Methods (from code) | Doc | Serving code |
|---|---|---|---|
| `/a/{domain}/api/application/v1/` `.../{app_id}/` | GET, GET | `application-structure.rst` | `v0_4.ApplicationResource` |
| `/a/{domain}/api/case/v1/` `.../{case_id}/` | GET, GET | `cases-v1.rst` | `v0_4.CommCareCaseResource` |
| `/a/{domain}/api/case/v2/` `.../{case_id}` `.../ext/{external_id}/` `.../bulk-fetch/` | GET, POST, PUT | `cases-v2.rst` | `hqcase.views.case_api`, `case_api_bulk_fetch` |
| `/a/{domain}/api/form/v1/` `.../{form_id}/` | GET, GET | `list-forms.rst`, `form-data.rst` | `v0_4.XFormInstanceResource` |
| `/a/{domain}/api/form_attachment/v1/{instance_id}/{attachment_id}` | GET | `form-data.rst` | `view_form_attachment` |
| `/a/{domain}/api/group/v1/` | list: GET, POST, PATCH; detail: GET, PUT, DELETE | `list-groups.rst`, `user-group.rst` | `v0_5.GroupResource` |
| `/a/{domain}/api/user/v1/` | list: GET, POST; detail: GET, PUT, DELETE | `list-mobile-workers.rst`, `mobile-worker.rst` | `v0_5.CommCareUserResource` |
| `/a/{domain}/api/web-user/v1/` | list: GET; detail: GET, PATCH | `list-webusers.rst`, `webuser.rst` | `v0_5.WebUserResource` |
| `/a/{domain}/api/invitation/v1/` | POST | `webuser.rst` | `v1_0.InvitationResource` |
| `/api/identity/v1/` | GET | `webuser.rst` | `v0_5.IdentityResource` |
| `/api/user_domains/v1/` | GET | `user-domain-list.rst` | `UserDomainsResource` |
| `/a/{domain}/api/bulk-user/v1/` | GET | `bulk-user.rst` | `v0_5.BulkUserResource` |
| `/a/{domain}/api/sso/v1/` | POST (list only) | `sso.rst` | `v0_4.SingleSignOnResource` |
| `/a/{domain}/api/location/v1/` | GET | `locations-v1.rst` | `locations.v0_5.LocationResource` |
| `/a/{domain}/api/location/v2/` | list: GET, POST, PATCH; detail: GET, PUT | `locations-v2.rst` | `locations.v0_6.LocationResource` |
| `/a/{domain}/api/location_type/v1/` | GET | `location-types.rst` | `locations.v0_5.LocationTypeResource` |
| `/a/{domain}/api/fixture/v1/` | GET | `fixture.rst` | `fixtures.v0_1.FixtureResource` |
| `/a/{domain}/api/lookup_table/v1/` | list: GET, POST; detail: GET, PUT, DELETE | `fixture.rst` | `fixtures.v0_1.LookupTableResource` |
| `/a/{domain}/api/lookup_table_item/v1/` | list: GET, POST; detail: GET, PUT, DELETE | `fixture.rst` | `fixtures.v0_1.LookupTableItemResource` |
| `/a/{domain}/fixtures/fixapi/` `.../status/{download_id}/` | POST, GET | `fixture.rst` | `corehq/apps/fixtures/views.py` |
| `/a/{domain}/api/simplereportconfiguration/v1/` | GET | `list-reports.rst` | `v0_5.SimpleReportConfigurationResource` |
| `/a/{domain}/api/configurablereportdata/v1/{report_id}/` | GET (**detail only** — `list_allowed_methods = []`) | `download-report-data.rst` | `v0_5.ConfigurableReportDataResource` |
| `/a/{domain}/api/det_export_instance/v1/` | GET | `det-exports.rst` | `v1_0.DETExportInstanceResource` |
| `/a/{domain}/api/messaging-event/v1/` `.../{event_id}/` | GET | `messaging-events.rst` | `resources.messaging_event.view.messaging_events` |
| `/a/{domain}/importer/excel/bulk_upload_api/` | POST | `bulk-upload-cases.rst` | case importer views |
| `/a/{domain}/apps/api/import_app/` `.../{app_id}/multimedia/` `.../multimedia/status/{processing_id}/` | POST, POST, GET | `import-app.rst` | app_manager views |
| `/a/{domain}/receiver/api/` `/a/{domain}/receiver/{app_id}/` | POST | `form-submission.rst` | `corehq/apps/receiverwrapper/urls.py` |

**Known discrepancy candidates** (verify, don't assume):
- `webuser.rst` documents `POST /api/web-user/v1/` and `.../activate/` + `.../deactivate/`, but `v0_5.WebUserResource` declares only `detail_allowed_methods = ['get', 'patch']` and inherits `list_allowed_methods = ['get']` from `v0_1.UserResource`. Find where activate/deactivate actually live.
- `user-group.rst` documents group writes; `v0_5.GroupResource` allows `PATCH` on the list endpoint (bulk) which the docs may not mention.
- `list-groups.rst` and `list-mobile-workers.rst` document a `format` parameter (`json`/`xml`); confirm tastypie serializer support per resource.

---

### Task 1: Tooling scaffold and valid root document

**Files:**
- Create: `docs/api/openapi/openapi.yaml`
- Create: `docs/api/openapi/redocly.yaml`
- Create: `docs/api/openapi/README.md`
- Modify: `package.json` (devDependencies, scripts)

**Interfaces:**
- Consumes: nothing.
- Produces: `docs/api/openapi/openapi.yaml` as the spec root; npm script `openapi:lint`.

- [ ] **Step 1: Install the toolchain**

```bash
yarn add --dev @redocly/cli
```

- [ ] **Step 2: Write the linter config**

Create `docs/api/openapi/redocly.yaml`:

```yaml
apis:
  commcare:
    root: ./openapi.yaml
extends:
  - recommended
rules:
  operation-operationId: error
  operation-summary: error
  operation-tags: error
  operation-4xx-response: warn
  no-unused-components: error
  path-params-defined: error
  tag-description: off
  info-license: off
```

- [ ] **Step 3: Write the root document**

Create `docs/api/openapi/openapi.yaml`. Note `paths: {}` for now — Task 3 adds the first real path.

```yaml
openapi: 3.0.3
info:
  title: CommCare HQ APIs
  version: '1.0'
  description: >-
    APIs for CommCare HQ, covering case and form data, user and location
    management, reports, form submission, and messaging events.

    Requires a CommCare Software Plan (Standard or above).
  contact:
    name: Dimagi Support
    url: https://dimagi.atlassian.net/wiki/spaces/commcarepublic/overview
servers:
  - url: https://{environment}
    description: CommCare HQ environment
    variables:
      environment:
        default: www.commcarehq.org
        enum:
          - www.commcarehq.org
          - india.commcarehq.org
          - swiss.commcarehq.org
        description: >-
          The CommCare HQ cloud environment hosting the project space.
tags:
  - name: Data
    description: >-
      APIs for building project-specific applications and integrations.
  - name: Users
    description: >-
      Managing mobile workers, web users, groups, and identity.
  - name: Submission
    description: >-
      OpenRosa-standard XForm submission.
  - name: SMS
    description: >-
      Messaging event history.
security:
  - ApiKey: []
  - Basic: []
  - OAuth2: []
paths: {}
```

- [ ] **Step 4: Add npm scripts**

In `package.json`, add to `scripts`:

```json
"openapi:lint": "redocly lint --config docs/api/openapi/redocly.yaml"
```

- [ ] **Step 5: Run the linter**

Run: `yarn openapi:lint`
Expected: PASS. If it complains that `paths` must be non-empty, that is a `recommended`-ruleset warning, not an error — confirm the exit code is 0. If it errors, add `paths` with a single placeholder that Task 3 replaces, and note it in the commit message.

- [ ] **Step 6: Write the README**

Create `docs/api/openapi/README.md`:

```markdown
# CommCare HQ OpenAPI specification

Machine-readable description of the public APIs documented in `docs/api/`.
The reST pages remain the prose narrative; this spec is the reference.

## Layout

- `openapi.yaml` — root document; `paths` are `$ref`s only
- `paths/` — one file per resource
- `components/` — shared security schemes, parameters, responses, schemas
- `dist/` — **generated, committed** artifacts

## Working on the spec

    yarn openapi:lint     # validate
    yarn openapi:bundle   # regenerate dist/openapi.bundled.yaml
    yarn openapi:docs     # regenerate dist/index.html
    yarn openapi:check    # verify dist/ matches source (what CI runs)

Always regenerate `dist/` in the same commit as a source change — CI
fails otherwise.

## Why dist/ is committed

readthedocs builds this repo with a Python-only environment
(`.readthedocs.yml`), so it cannot run the Node bundler. CI regenerates
and diffs the artifacts to guarantee they are current.

**On a merge conflict in `dist/`, do not hand-merge.** Take either side,
then run `yarn openapi:bundle && yarn openapi:docs` and commit the result.

## Scope

The OTA restore API is intentionally excluded: it returns opaque,
application-specific CaseXML. Admin and internal APIs are also excluded.
```

- [ ] **Step 7: Commit**

```bash
npx prettier --write docs/api/openapi/openapi.yaml docs/api/openapi/redocly.yaml docs/api/openapi/README.md
git add package.json yarn.lock docs/api/openapi/
git commit -m "feat(openapi): scaffold spec root and redocly toolchain"
```

---

### Task 2: Shared components

**Files:**
- Create: `docs/api/openapi/components/securitySchemes.yaml`
- Create: `docs/api/openapi/components/parameters.yaml`
- Create: `docs/api/openapi/components/responses.yaml`
- Create: `docs/api/openapi/components/schemas/pagination.yaml`
- Modify: `docs/api/openapi/openapi.yaml`

**Interfaces:**
- Consumes: `openapi.yaml` from Task 1.
- Produces: these `$ref` targets, used by every later path file —
  `#/components/securitySchemes/{ApiKey,Basic,OAuth2}`;
  `#/components/parameters/{Domain,Limit,Offset,Format}`;
  `#/components/responses/{BadRequest,Unauthorized,Forbidden,NotFound,TooManyRequests,ServerError}`;
  `#/components/schemas/{PaginationMeta,CursorMeta,Error}`.

- [ ] **Step 1: Write the security schemes**

Create `docs/api/openapi/components/securitySchemes.yaml`:

```yaml
ApiKey:
  type: apiKey
  in: header
  name: Authorization
  description: >-
    API key authentication. Send the header as
    `Authorization: ApiKey <email>:<api_key>`.

    This is not a registered HTTP authentication scheme, so it is
    described here as an apiKey header rather than as `type: http`.
    Generate a key under Account Settings in CommCare HQ.
Basic:
  type: http
  scheme: basic
  description: >-
    HTTP Basic authentication with a CommCare username and password.
    For mobile workers the username is `<username>@<domain>.commcarehq.org`.
OAuth2:
  type: http
  scheme: bearer
  description: >-
    OAuth2 bearer token, sent as `Authorization: Bearer <token>`.
```

- [ ] **Step 2: Write the shared parameters**

Create `docs/api/openapi/components/parameters.yaml`. Every path parameter carries an `example` — Task 4's test depends on it.

```yaml
Domain:
  name: domain
  in: path
  required: true
  description: The project space name.
  example: demo
  schema:
    type: string
Limit:
  name: limit
  in: query
  required: false
  description: 'Maximum number of records to return. Default: 20. Maximum: 1000.'
  example: 100
  schema:
    type: integer
    minimum: 1
    maximum: 1000
    default: 20
Offset:
  name: offset
  in: query
  required: false
  description: 'Number of records to skip. Default: 0.'
  example: 100
  schema:
    type: integer
    minimum: 0
    default: 0
Format:
  name: format
  in: query
  required: false
  description: Response serialization format.
  example: json
  schema:
    type: string
    enum: [json, xml]
    default: json
```

- [ ] **Step 3: Write the shared responses and error schema**

Create `docs/api/openapi/components/responses.yaml`:

```yaml
BadRequest:
  description: The request was malformed or a parameter value was invalid.
  content:
    application/json:
      schema:
        $ref: './schemas/pagination.yaml#/Error'
Unauthorized:
  description: >-
    Authentication credentials were missing or invalid. Note that CommCare
    also returns 401 with `{"error": "not authorized"}` for some
    permission failures.
  content:
    application/json:
      schema:
        $ref: './schemas/pagination.yaml#/Error'
Forbidden:
  description: >-
    The authenticated user lacks the permission required for this endpoint.
  content:
    application/json:
      schema:
        $ref: './schemas/pagination.yaml#/Error'
NotFound:
  description: The requested resource does not exist in this project space.
  content:
    application/json:
      schema:
        $ref: './schemas/pagination.yaml#/Error'
TooManyRequests:
  description: >-
    The request was rate limited. Back off and retry. Rate limits are
    applied per user and project space.
  content:
    application/json:
      schema:
        $ref: './schemas/pagination.yaml#/Error'
ServerError:
  description: An unexpected error occurred.
  content:
    application/json:
      schema:
        $ref: './schemas/pagination.yaml#/Error'
```

- [ ] **Step 4: Write the pagination and error schemas**

Create `docs/api/openapi/components/schemas/pagination.yaml`:

```yaml
Error:
  type: object
  properties:
    error:
      type: string
      description: Human-readable description of the failure.
      example: not authorized
PaginationMeta:
  type: object
  description: >-
    Offset-based pagination metadata returned by most list endpoints.
  properties:
    limit:
      type: integer
      example: 20
    offset:
      type: integer
      example: 0
    next:
      type: string
      nullable: true
      description: >-
        Relative URL of the next page, or null on the last page.
      example: /a/demo/api/form/v1/?limit=20&offset=20
    previous:
      type: string
      nullable: true
      description: Relative URL of the previous page, or null on the first page.
      example: null
    total_count:
      type: integer
      description: Total number of matching records.
      example: 6909
CursorMeta:
  type: object
  description: >-
    Cursor-based pagination metadata. Used only by the messaging events
    endpoint. The cursor is opaque and must not be constructed by clients.
  properties:
    limit:
      type: integer
      example: 20
    next:
      type: string
      nullable: true
      description: >-
        Relative URL of the next page including an opaque `cursor`
        parameter, or null when no further records exist.
      example: /a/demo/api/messaging-event/v1/?cursor=ZGF0ZS5ndGU9MjAyMC0wNS0xN1Q
PaginatedResponse:
  type: object
  description: >-
    Standard list envelope. Resource-specific responses narrow `objects`
    using allOf.
  required: [meta, objects]
  properties:
    meta:
      $ref: '#/PaginationMeta'
    objects:
      type: array
      items:
        type: object
```

- [ ] **Step 5: Wire components into the root document**

In `docs/api/openapi/openapi.yaml`, add a top-level `components` section between the `tags:` block and the `security:` block:

```yaml
components:
  securitySchemes:
    ApiKey:
      $ref: './components/securitySchemes.yaml#/ApiKey'
    Basic:
      $ref: './components/securitySchemes.yaml#/Basic'
    OAuth2:
      $ref: './components/securitySchemes.yaml#/OAuth2'
```

Parameters, responses, and schemas are referenced directly by relative
file path from the path files, so they do not need entries here. This
avoids `no-unused-components` errors on components not yet consumed.

- [ ] **Step 6: Lint**

Run: `yarn openapi:lint`
Expected: PASS, exit code 0.

- [ ] **Step 7: Commit**

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/
git commit -m "feat(openapi): add shared security, parameter, response, and pagination components"
```

---

### Task 3: First resource end-to-end (group) plus spec-consistency tests

This task establishes the pattern every later resource task follows. It is
deliberately the smallest resource that has both read and write operations.

**Files:**
- Create: `docs/api/openapi/paths/group.yaml`
- Create: `docs/api/openapi/components/schemas/group.yaml`
- Create: `corehq/apps/api/tests/test_openapi_spec.py`
- Modify: `docs/api/openapi/openapi.yaml`
- Test: `corehq/apps/api/tests/test_openapi_spec.py`

**Interfaces:**
- Consumes: components from Task 2.
- Produces: `_load_spec()` and `_iter_operations()` helpers in
  `test_openapi_spec.py`, reused by Task 4:
  - `_load_spec() -> dict` — parses `docs/api/openapi/openapi.yaml` with
    all `$ref`s resolved.
  - `_iter_operations(spec) -> Iterator[tuple[str, str, dict]]` — yields
    `(path, http_method, operation_dict)` for every operation.

- [ ] **Step 1: Read the source material**

Read `docs/api/list-groups.rst` (all 83 lines) and `docs/api/user-group.rst`
(all 233 lines). Then read `corehq/apps/api/resources/v0_5.py:655-700` and
`corehq/apps/api/resources/v0_4.py:234-258`.

Record in a scratch note: the documented query parameters, the documented
response fields, and the allowed methods declared in code
(`list_allowed_methods = ['get', 'post', 'patch']`,
`detail_allowed_methods = ['get', 'put', 'delete']`).

- [ ] **Step 2: Write the failing spec-consistency test**

Create `corehq/apps/api/tests/test_openapi_spec.py`:

```python
"""Structural tests for the OpenAPI specification in docs/api/openapi/."""
import os
from collections.abc import Iterator

import pytest
import yaml
from django.conf import settings

SPEC_ROOT = os.path.join(settings.FILEPATH, 'docs', 'api', 'openapi')
SPEC_PATH = os.path.join(SPEC_ROOT, 'openapi.yaml')
HTTP_METHODS = frozenset(
    ['get', 'put', 'post', 'delete', 'patch', 'head', 'options', 'trace']
)


def _resolve_refs(node, base_dir):
    """Recursively inline every ``$ref`` so the spec can be inspected as one dict.

    Handles both local refs (``#/Foo``) and relative file refs
    (``./components/schemas/group.yaml#/Group``). Cycles are not expected
    in this spec; a cyclic ``$ref`` will raise RecursionError, which is an
    acceptable failure mode for a test.
    """
    if isinstance(node, list):
        return [_resolve_refs(item, base_dir) for item in node]
    if not isinstance(node, dict):
        return node
    if set(node) == {'$ref'}:
        ref = node['$ref']
        file_part, _, fragment = ref.partition('#')
        if file_part:
            target_path = os.path.normpath(os.path.join(base_dir, file_part))
            with open(target_path) as f:
                document = yaml.safe_load(f)
            next_base = os.path.dirname(target_path)
        else:
            with open(SPEC_PATH) as f:
                document = yaml.safe_load(f)
            next_base = SPEC_ROOT
        for key in [p for p in fragment.split('/') if p]:
            document = document[key]
        return _resolve_refs(document, next_base)
    return {key: _resolve_refs(value, base_dir) for key, value in node.items()}


def _load_spec():
    with open(SPEC_PATH) as f:
        return _resolve_refs(yaml.safe_load(f), SPEC_ROOT)


def _iter_operations(spec) -> Iterator[tuple[str, str, dict]]:
    for path, path_item in spec['paths'].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


@pytest.fixture(scope='module')
def spec():
    return _load_spec()


def test_spec_parses_and_refs_resolve(spec):
    assert spec['openapi'] == '3.0.3'
    assert spec['paths'], 'spec declares no paths'


def test_operation_ids_are_unique(spec):
    seen = {}
    for path, method, operation in _iter_operations(spec):
        operation_id = operation['operationId']
        assert operation_id not in seen, (
            f'duplicate operationId {operation_id!r}: '
            f'{seen[operation_id]} and {method.upper()} {path}'
        )
        seen[operation_id] = f'{method.upper()} {path}'


def test_every_operation_has_agent_facing_fields(spec):
    known_tags = {tag['name'] for tag in spec['tags']}
    for path, method, operation in _iter_operations(spec):
        where = f'{method.upper()} {path}'
        assert operation.get('summary'), f'{where} has no summary'
        assert operation.get('tags'), f'{where} has no tags'
        assert operation.get('responses'), f'{where} has no responses'
        unknown = set(operation['tags']) - known_tags
        assert not unknown, f'{where} uses undeclared tags: {unknown}'


def test_every_path_parameter_has_an_example(spec):
    """Task 4's URL-resolution test builds real URLs from these examples."""
    for path, path_item in spec['paths'].items():
        parameters = list(path_item.get('parameters', []))
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                parameters.extend(operation.get('parameters', []))
        for parameter in parameters:
            if parameter.get('in') == 'path':
                assert 'example' in parameter, (
                    f'path parameter {parameter["name"]!r} on {path} '
                    'has no example'
                )
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v`
Expected: FAIL on `test_spec_parses_and_refs_resolve` with
`AssertionError: spec declares no paths`, because `paths` is still `{}`.

- [ ] **Step 4: Write the group schema**

Create `docs/api/openapi/components/schemas/group.yaml`. Field names come
from the sample output at `docs/api/list-groups.rst:66-83` and must be
verified against `v0_4.GroupResource` field declarations.

```yaml
Group:
  type: object
  properties:
    id:
      type: string
      description: Group UUID.
      example: 1eb59d6938fc7e510254d8c2f63d944f
    name:
      type: string
      description: Group name, for example a health district.
      example: Wozzle
    domain:
      type: string
      description: Project space the group belongs to.
      example: demo
    case_sharing:
      type: boolean
      description: Whether members share cases owned by the group.
      example: false
    reporting:
      type: boolean
      description: Whether the group is used for reporting rollups.
      example: true
    metadata:
      type: object
      additionalProperties: true
      description: Arbitrary key/value metadata attached to the group.
    path:
      type: array
      items:
        type: string
      description: Legacy hierarchy path. Normally empty.
    users:
      type: array
      items:
        type: string
      description: User UUIDs of group members.
      example:
        - 91da6b1c78699adfb8679b741caf9f00
GroupList:
  allOf:
    - $ref: './pagination.yaml#/PaginatedResponse'
    - type: object
      properties:
        objects:
          type: array
          items:
            $ref: '#/Group'
GroupWrite:
  type: object
  description: Payload for creating or replacing a group.
  required: [name]
  properties:
    name:
      type: string
      example: Wozzle
    case_sharing:
      type: boolean
      example: false
    reporting:
      type: boolean
      example: true
    metadata:
      type: object
      additionalProperties: true
    users:
      type: array
      items:
        type: string
      example:
        - 91da6b1c78699adfb8679b741caf9f00
```

- [ ] **Step 5: Write the group paths**

Create `docs/api/openapi/paths/group.yaml`. Methods come from code, not
from the docs.

```yaml
List:
  parameters:
    - $ref: '../components/parameters.yaml#/Domain'
  get:
    operationId: listGroups
    summary: List user groups
    description: >-
      Returns groups the authenticated user is permitted to see. Requires
      the Edit Mobile Workers permission.
    tags: [Users]
    parameters:
      - $ref: '../components/parameters.yaml#/Limit'
      - $ref: '../components/parameters.yaml#/Offset'
      - $ref: '../components/parameters.yaml#/Format'
    responses:
      '200':
        description: A page of groups.
        content:
          application/json:
            schema:
              $ref: '../components/schemas/group.yaml#/GroupList'
      '401':
        $ref: '../components/responses.yaml#/Unauthorized'
      '403':
        $ref: '../components/responses.yaml#/Forbidden'
      '429':
        $ref: '../components/responses.yaml#/TooManyRequests'
  post:
    operationId: createGroup
    summary: Create a user group
    tags: [Users]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '../components/schemas/group.yaml#/GroupWrite'
    responses:
      '201':
        description: The group was created.
        content:
          application/json:
            schema:
              $ref: '../components/schemas/group.yaml#/Group'
      '400':
        $ref: '../components/responses.yaml#/BadRequest'
      '401':
        $ref: '../components/responses.yaml#/Unauthorized'
      '403':
        $ref: '../components/responses.yaml#/Forbidden'
  patch:
    operationId: bulkUpdateGroups
    summary: Bulk create or update groups
    description: >-
      Accepts a list of group payloads. Declared by
      `v0_5.GroupResource.patch_list`.
    tags: [Users]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              objects:
                type: array
                items:
                  $ref: '../components/schemas/group.yaml#/GroupWrite'
    responses:
      '202':
        description: The bulk update was accepted.
      '400':
        $ref: '../components/responses.yaml#/BadRequest'
      '401':
        $ref: '../components/responses.yaml#/Unauthorized'
Detail:
  parameters:
    - $ref: '../components/parameters.yaml#/Domain'
    - name: group_id
      in: path
      required: true
      description: Group UUID.
      example: 1eb59d6938fc7e510254d8c2f63d944f
      schema:
        type: string
  get:
    operationId: getGroup
    summary: Retrieve a single user group
    tags: [Users]
    responses:
      '200':
        description: The group.
        content:
          application/json:
            schema:
              $ref: '../components/schemas/group.yaml#/Group'
      '404':
        $ref: '../components/responses.yaml#/NotFound'
  put:
    operationId: replaceGroup
    summary: Replace a user group
    tags: [Users]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '../components/schemas/group.yaml#/GroupWrite'
    responses:
      '200':
        description: The updated group.
        content:
          application/json:
            schema:
              $ref: '../components/schemas/group.yaml#/Group'
      '400':
        $ref: '../components/responses.yaml#/BadRequest'
      '404':
        $ref: '../components/responses.yaml#/NotFound'
  delete:
    operationId: deleteGroup
    summary: Delete a user group
    tags: [Users]
    responses:
      '204':
        description: The group was deleted.
      '404':
        $ref: '../components/responses.yaml#/NotFound'
```

- [ ] **Step 6: Reference the paths from the root document**

In `docs/api/openapi/openapi.yaml`, replace `paths: {}` with:

```yaml
paths:
  /a/{domain}/api/group/v1/:
    $ref: './paths/group.yaml#/List'
  /a/{domain}/api/group/v1/{group_id}/:
    $ref: './paths/group.yaml#/Detail'
```

- [ ] **Step 7: Run lint and tests**

Run: `yarn openapi:lint && uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v`
Expected: lint PASS; all four tests PASS.

- [ ] **Step 8: Record any discrepancies**

Create `docs/superpowers/specs/2026-08-17-openapi-discrepancies.md` with a
heading and the group findings. Use this exact format so later tasks append
consistently:

```markdown
# OpenAPI cross-check: docs vs. code discrepancies

Generated while writing the OpenAPI spec. The spec records what the **code**
does. Each item below is a place where `docs/api/*.rst` disagrees, for human
triage. Nothing here has been changed in the reST docs.

## group/v1 (`list-groups.rst`, `user-group.rst`)

- **`PATCH` on the list endpoint is undocumented.** `v0_5.GroupResource.Meta`
  declares `list_allowed_methods = ['get', 'post', 'patch']`; neither reST
  page mentions bulk PATCH. Spec includes it as `bulkUpdateGroups`.
- *(append further findings here as they are confirmed)*
```

If a bullet turns out not to be a real discrepancy after reading the code,
delete it rather than softening it.

- [ ] **Step 9: Commit**

```bash
npx prettier --write docs/api/openapi/
uv run ruff check corehq/apps/api/tests/test_openapi_spec.py
git add docs/api/openapi/ corehq/apps/api/tests/test_openapi_spec.py docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add group resource and spec consistency tests"
```

---

### Task 4: URL-resolution test

This is the test with real teeth: it fails when an endpoint is renamed or
removed, rather than letting the spec quietly lie.

**Files:**
- Modify: `corehq/apps/api/tests/test_openapi_spec.py`
- Test: `corehq/apps/api/tests/test_openapi_spec.py`

**Interfaces:**
- Consumes: `_load_spec()`, `_iter_operations()`, `HTTP_METHODS` from Task 3.
- Produces: `_concrete_url(path, path_item) -> str`, used by no later task
  but relied on by every later task's test run.

- [ ] **Step 1: Write the failing test**

Append to `corehq/apps/api/tests/test_openapi_spec.py`:

```python
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve


def _concrete_url(path, path_item):
    """Substitute each path parameter's ``example`` to build a resolvable URL."""
    examples = {}
    parameters = list(path_item.get('parameters', []))
    for method, operation in path_item.items():
        if method in HTTP_METHODS:
            parameters.extend(operation.get('parameters', []))
    for parameter in parameters:
        if parameter.get('in') == 'path':
            examples[parameter['name']] = str(parameter['example'])
    return path.format(**examples)


class TestSpecPathsResolve(SimpleTestCase):
    """Every path in the spec must map to a real Django URL pattern."""

    def test_all_paths_resolve(self):
        spec = _load_spec()
        unresolvable = []
        for path, path_item in spec['paths'].items():
            url = _concrete_url(path, path_item)
            try:
                resolve(url)
            except Resolver404:
                unresolvable.append(f'{path} (tried {url})')
        assert not unresolvable, (
            'spec paths that do not resolve against Django URLconf:\n  '
            + '\n  '.join(unresolvable)
        )
```

- [ ] **Step 2: Run it**

Run: `uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py::TestSpecPathsResolve -v`
Expected: PASS — the group paths from Task 3 are real. If it FAILS, the
group path strings are wrong; fix `openapi.yaml`, not the test.

- [ ] **Step 3: Prove the test has teeth**

Temporarily change the group list path in `openapi.yaml` to
`/a/{domain}/api/group/v9/:` and re-run the test.
Expected: FAIL listing `/a/{domain}/api/group/v9/ (tried /a/demo/api/group/v9/)`.
Then revert the change and re-run to confirm PASS.

This step is not optional — a resolution test that cannot fail is worse
than no test, because it manufactures false confidence.

- [ ] **Step 4: Commit**

```bash
uv run ruff check corehq/apps/api/tests/test_openapi_spec.py
git add corehq/apps/api/tests/test_openapi_spec.py
git commit -m "test(openapi): assert every spec path resolves against Django URLconf"
```

---

### Task 5: Bundled artifacts and the drift guard

**Files:**
- Create: `docs/api/openapi/dist/openapi.bundled.yaml` (generated)
- Create: `docs/api/openapi/dist/index.html` (generated)
- Create: `scripts/check-openapi-dist.sh`
- Modify: `package.json`

**Interfaces:**
- Consumes: the spec root from Tasks 1–3.
- Produces: npm scripts `openapi:bundle`, `openapi:docs`, `openapi:check`;
  `scripts/check-openapi-dist.sh` used by CI in Task 6.

- [ ] **Step 1: Add the build scripts**

In `package.json` `scripts`:

```json
"openapi:bundle": "redocly bundle --config docs/api/openapi/redocly.yaml commcare -o docs/api/openapi/dist/openapi.bundled.yaml",
"openapi:docs": "redocly build-docs --config docs/api/openapi/redocly.yaml commcare -o docs/api/openapi/dist/index.html",
"openapi:check": "./scripts/check-openapi-dist.sh"
```

- [ ] **Step 2: Generate the artifacts**

```bash
mkdir -p docs/api/openapi/dist
yarn openapi:bundle
yarn openapi:docs
```

Expected: both files exist and are non-empty. Confirm
`docs/api/openapi/dist/openapi.bundled.yaml` contains no `$ref` pointing at
a relative file path (`grep -c "\.yaml#" docs/api/openapi/dist/openapi.bundled.yaml`
should print `0`).

- [ ] **Step 3: Write the drift-guard script**

Create `scripts/check-openapi-dist.sh`:

```bash
#!/bin/bash
# Verify the committed OpenAPI artifacts in docs/api/openapi/dist/ match the
# source spec. Regenerating into a temp dir and diffing means a spec change
# cannot merge without its artifacts being refreshed.
#
# If this fails: run `yarn openapi:bundle && yarn openapi:docs` and commit.
set -euo pipefail

DIST='docs/api/openapi/dist'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

npx redocly bundle --config docs/api/openapi/redocly.yaml commcare \
    -o "$TMP/openapi.bundled.yaml"
npx redocly build-docs --config docs/api/openapi/redocly.yaml commcare \
    -o "$TMP/index.html"

status=0
for file in openapi.bundled.yaml index.html; do
    if ! diff -q "$DIST/$file" "$TMP/$file" >/dev/null 2>&1; then
        echo "ERROR: $DIST/$file is stale."
        status=1
    fi
done

if [ "$status" -ne 0 ]; then
    echo
    echo 'Regenerate with: yarn openapi:bundle && yarn openapi:docs'
fi
exit "$status"
```

Then: `chmod +x scripts/check-openapi-dist.sh`

- [ ] **Step 4: Verify the guard passes, then prove it fails**

Run: `yarn openapi:check`
Expected: exit 0, no output.

Now append a comment line to `docs/api/openapi/dist/openapi.bundled.yaml`
and re-run.
Expected: FAIL with `ERROR: docs/api/openapi/dist/openapi.bundled.yaml is stale.`
Then run `yarn openapi:bundle` to restore it and confirm the check passes again.

Note: `build-docs` output may embed a timestamp or version string, which
would make the diff fail spuriously. If Step 4's first run fails on
`index.html` with only such a line differing, add a normalising `sed` to
the script for that line and record why in a comment. Do **not** simply
drop `index.html` from the check.

- [ ] **Step 5: Commit**

```bash
git add package.json scripts/check-openapi-dist.sh docs/api/openapi/dist/
git commit -m "build(openapi): add bundle, docs, and staleness-check scripts"
```

---

### Task 6: CI job

**Files:**
- Modify: `.github/workflows/lint.yml`

**Interfaces:**
- Consumes: `openapi:lint` and `openapi:check` scripts from Tasks 1 and 5.
- Produces: a `lint-openapi` CI job.

- [ ] **Step 1: Read the existing pattern**

Read `.github/workflows/lint.yml` in full, paying attention to the
`lint-javascript` job — copy its `harden-runner`, checkout, Node setup, and
dependency-install steps verbatim rather than inventing new ones, including
the pinned action SHAs.

- [ ] **Step 2: Add the job**

Append a `lint-openapi` job mirroring `lint-javascript`'s setup steps, then:

```yaml
      - name: Validate OpenAPI spec
        run: yarn openapi:lint

      - name: Check committed OpenAPI artifacts are current
        run: yarn openapi:check
```

Unlike the Python and JS lint jobs, do **not** gate this on
`changed-files` — the whole point is that a change to
`corehq/apps/api/urls.py` with no spec change should still be checked. The
job is fast enough to run unconditionally.

- [ ] **Step 3: Validate the workflow locally**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/lint.yml')); print('valid')"`
Expected: `valid`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/lint.yml
git commit -m "ci(openapi): lint spec and verify bundled artifacts are current"
```

---

### Task 7: Publish through Sphinx

**Files:**
- Modify: `docs/conf.py`
- Modify: `docs/api/index.rst`

**Interfaces:**
- Consumes: `docs/api/openapi/dist/index.html` from Task 5.
- Produces: the published reference page at `<docs-root>/openapi/index.html`.

- [ ] **Step 1: Read the current config**

Read `docs/conf.py`. There is currently no `html_extra_path` or
`html_static_path`. Note `exclude_patterns = ['_build']` at line 66.

- [ ] **Step 2: Add the extra path**

In `docs/conf.py`, after `exclude_patterns`:

```python
# The OpenAPI reference is a self-contained Redoc page, generated by
# `yarn openapi:docs` and committed under docs/api/openapi/dist/.
# readthedocs builds with a Python-only environment and cannot run the
# Node bundler, so the artifact is committed and CI verifies it is current.
# html_extra_path copies it verbatim without adding it to any toctree,
# which keeps the strict docs build (scripts/test-make-docs.sh) warning-free.
html_extra_path = ['api/openapi/dist']
```

Because `html_extra_path` copies directory *contents*, `dist/index.html`
would land at the docs root and collide with Sphinx's own `index.html`.
Prevent this by nesting: create `docs/api/openapi/dist/openapi/` as the
output directory instead.

- [ ] **Step 3: Fix the output location to avoid the index.html collision**

Update the two npm scripts in `package.json` so the docs artifact is
written one level deeper:

```json
"openapi:docs": "redocly build-docs --config docs/api/openapi/redocly.yaml commcare -o docs/api/openapi/dist/openapi/index.html"
```

Update `scripts/check-openapi-dist.sh` to match: change the `build-docs`
output to `"$TMP/openapi/index.html"` and the loop to compare
`openapi/index.html` rather than `index.html`.

Then regenerate and remove the old file:

```bash
rm -f docs/api/openapi/dist/index.html
yarn openapi:docs
yarn openapi:check
```

Expected: check passes; `docs/api/openapi/dist/openapi/index.html` exists.

- [ ] **Step 4: Link it from the API index**

In `docs/api/index.rst`, immediately after the "Table of contents" heading's
introductory text and before the `Data APIs` section, add:

```rst
The complete machine-readable reference for these APIs is published as an
`OpenAPI 3.0 specification <../openapi/index.html>`_, browsable as an
interactive reference. The pages below remain the narrative documentation.
```

- [ ] **Step 5: Build the docs and confirm zero new warnings**

```bash
rm -rf docs/_build
./scripts/test-make-docs.sh
```

Expected: exit 0. The script fails on *any* un-whitelisted warning, so a
non-empty `make-docs-errors.log` means this step is not done. A likely
warning is Sphinx complaining the link target is not a document — if that
occurs, the `\`... <../openapi/index.html>\`_` form is being parsed as a
doc reference; use `:download:` or a raw external link instead, and note
which worked.

- [ ] **Step 6: Confirm the artifact landed in the build**

Run: `ls docs/_build/html/openapi/index.html`
Expected: the file exists.

- [ ] **Step 7: Commit**

```bash
git add docs/conf.py docs/api/index.rst package.json scripts/check-openapi-dist.sh docs/api/openapi/dist/
git commit -m "docs(openapi): publish Redoc reference through Sphinx"
```

---

## Resource tasks 8–16

Tasks 8 through 16 each add one group of resources. They share one
procedure, written out in full here — **this is the procedure, not a
cross-reference**. Each task below then carries its own concrete source
material, paths, methods, and pitfalls, and repeats the procedure as its
own checkbox list so it can be tracked and executed standalone.

**The shared seven-step cycle:**

1. **Read the source.** Read the listed reST doc(s) end to end, then the
   listed serving code. Note documented params, documented response fields,
   and the allowed methods declared in code.
2. **Write the schema file(s)** under `components/schemas/`, with a
   `description` and `example` on every property. Field names come from the
   reST sample output, verified against the resource's field declarations.
   List responses use the `allOf` + `PaginatedResponse` pattern from
   `components/schemas/group.yaml`.
3. **Write the path file** under `paths/`, one operation per method the
   **code** allows. Every operation gets `operationId`, `summary`, `tags`,
   responses including the shared error refs, and `$ref`s to shared
   parameters. Every path parameter gets an `example`.
4. **Add `$ref` entries** for the new paths in `openapi.yaml`.
5. **Regenerate artifacts:** `yarn openapi:bundle && yarn openapi:docs`
6. **Run the full gate:**
   `yarn openapi:lint && yarn openapi:check && uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v`
   All must pass. The URL-resolution test is what catches a wrong path.
7. **Append confirmed discrepancies** to
   `docs/superpowers/specs/2026-08-17-openapi-discrepancies.md` under a
   `## <resource>` heading, then `npx prettier --write docs/api/openapi/`
   and commit.

Per-task specifics follow.

---

### Task 8: Cases v1

**Files:**
- Create: `docs/api/openapi/paths/case-v1.yaml`, `docs/api/openapi/components/schemas/case.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`
- Test: existing `corehq/apps/api/tests/test_openapi_spec.py`

**Interfaces:**
- Consumes: components from Task 2; the pattern from Task 3.
- Produces: `components/schemas/case.yaml#/Case` and `#/CaseList`, reused by Task 9.

**Source:** `docs/api/cases-v1.rst` (414 lines). Code: `corehq/apps/api/resources/v0_4.py:186-233`, `v0_3.py`.

**Paths:** `/a/{domain}/api/case/v1/` (GET), `/a/{domain}/api/case/v1/{case_id}/` (GET).

**Query parameters** (documented at `cases-v1.rst:36-100`, all optional):
`owner_id`, `user_id`, `type`, `closed`, `indexed_on_start`, `indexed_on_end`,
`date_modified_start`, `date_modified_end`, `server_date_modified_start`,
`server_date_modified_end`, `name`, `limit`, `offset`, `external_id`,
plus `order_by` accepting `indexed_on` or `server_date_modified`, plus
`format` (`json`/`xml`) and the `properties=all` / `indices=all` flags shown
at `cases-v1.rst:14`.

**Response fields** (documented at `cases-v1.rst:114-144`): `case_id`,
`username`, `user_id`, `owner_id`, `case_name`, `external_id`, `case_type`,
`date_opened`, `date_modified`, `closed`, `date_closed`, plus `properties`
and `indices` objects.

**Watch for:** the date parameters are naive ISO-8601 without timezone in
the examples (`2012-01-01T06:05:42`); type them as
`type: string, format: date-time` and say so in the description rather than
implying timezone handling the API may not do.

- [ ] **Step 1: Read the source** — `docs/api/cases-v1.rst` in full, then `corehq/apps/api/resources/v0_4.py:186-233` and `v0_3.py`. Note documented params, documented response fields, and the allowed methods declared in code.
- [ ] **Step 2: Write** `docs/api/openapi/components/schemas/case.yaml` with `Case` and `CaseList`, a `description` and `example` on every property, `CaseList` built as `allOf` + `PaginatedResponse` following `components/schemas/group.yaml`.
- [ ] **Step 3: Write** `docs/api/openapi/paths/case-v1.yaml` — GET list and GET detail only, each with `operationId`, `summary`, `tags: [Data]`, shared error `$ref`s, and an `example` on every path parameter.
- [ ] **Step 4: Add** `/a/{domain}/api/case/v1/` and `/a/{domain}/api/case/v1/{case_id}/` `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. A `TestSpecPathsResolve` failure means a path string is wrong — fix the spec.

- [ ] **Step 7: Record discrepancies and commit**

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add case v1 resource"
```

---

### Task 9: Cases v2

**Files:**
- Create: `docs/api/openapi/paths/case-v2.yaml`, `docs/api/openapi/components/schemas/case-v2.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: `components/schemas/case.yaml` from Task 8 where field shapes overlap.
- Produces: nothing later tasks depend on.

**Source:** `docs/api/cases-v2.rst` (711 lines — the largest). Code:
`corehq/apps/hqcase/views.py` (`case_api`, `case_api_bulk_fetch`),
`corehq/apps/api/urls.py:149-153`.

This is the heaviest task; budget accordingly. Eight operations:

| Path | Method | operationId | Doc line |
|---|---|---|---|
| `/a/{domain}/api/case/v2/` | GET | `listCasesV2` | 240 |
| `/a/{domain}/api/case/v2/{case_id}` | GET | `getCaseV2` | 386 |
| `/a/{domain}/api/case/v2/ext/{external_id}/` | GET | `getCaseV2ByExternalId` | 387 |
| `/a/{domain}/api/case/v2/bulk-fetch/` | POST | `bulkFetchCasesV2` | 468 |
| `/a/{domain}/api/case/v2/` | POST | `createCasesV2` | 535, 593 |
| `/a/{domain}/api/case/v2/{case_id}` | PUT | `updateCaseV2` | 569 |
| `/a/{domain}/api/case/v2/ext/{external_id}/` | PUT | `updateCaseV2ByExternalId` | 570 |

**Two things need explicit, careful description text:**

1. **Comma-separated multi-fetch** (`cases-v2.rst:455`):
   `GET /a/{domain}/api/case/v2/<case_id>,<case_id>,<case_id>`. This shares
   the `{case_id}` path template with single-case GET. Model it as the same
   path with one parameter, and in the parameter description state that
   multiple comma-separated IDs return multiple cases. Do **not** create a
   second path — OpenAPI would treat it as a duplicate. Set
   `style: simple`, `explode: false` and note the semantics in the
   `description`, because agents otherwise pass a list and get it wrong.
2. **Payload shape determines bulk vs. single** (`cases-v2.rst:542`): a
   *list* body to `POST`/`PUT` means bulk. Use `oneOf` with a single-object
   schema and an array schema, and say plainly in the operation description
   that a list triggers bulk handling.

**Also note:** `urls.py:151-152` makes the trailing slash *optional*
(`case/v2/?$`). The spec declares the no-trailing-slash form for detail
paths (matching the doc) and the trailing-slash form for the list path.
Verify both resolve in the Task 4 test.

- [ ] **Step 1: Read the source** — `docs/api/cases-v2.rst` in full (711 lines), then `corehq/apps/hqcase/views.py` (`case_api`, `case_api_bulk_fetch`) and `corehq/apps/api/urls.py:149-153`.
- [ ] **Step 2: Write** `docs/api/openapi/components/schemas/case-v2.yaml`, reusing `case.yaml` shapes where they overlap; `description` and `example` on every property.
- [ ] **Step 3: Write** `docs/api/openapi/paths/case-v2.yaml` — all eight operations from the table above, with the comma-separated multi-fetch and the list-means-bulk `oneOf` described explicitly as noted.
- [ ] **Step 4: Add** the four `/a/{domain}/api/case/v2/...` `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. Pay attention to the optional-trailing-slash paths here.

- [ ] **Step 7: Record discrepancies and commit**

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add case v2 resource"
```

---

### Task 10: Forms and form submission

**Files:**
- Create: `docs/api/openapi/paths/form.yaml`, `docs/api/openapi/paths/submission.yaml`, `docs/api/openapi/components/schemas/form.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: components from Task 2.
- Produces: nothing later tasks depend on.

**Source:** `docs/api/list-forms.rst` (181), `docs/api/form-data.rst` (135),
`docs/api/form-submission.rst` (357). Code:
`corehq/apps/api/resources/v0_4.py:64-185`, `corehq/apps/api/object_fetch_api.py`,
`corehq/apps/receiverwrapper/urls.py`.

**Paths:**
- `/a/{domain}/api/form/v1/` GET — `listForms`
- `/a/{domain}/api/form/v1/{form_id}/` GET — `getForm`
- `/a/{domain}/api/form_attachment/v1/{instance_id}/{attachment_id}` GET — `getFormAttachment`
- `/a/{domain}/receiver/api/` POST — `submitForm`
- `/a/{domain}/receiver/{app_id}/` POST — `submitFormForApp`

**Query parameters for `listForms`** (`list-forms.rst:35-74`): `xmlns`,
`limit`, `offset`, `indexed_on_start`, `indexed_on_end`, `received_on_start`,
`received_on_end`, `appVersion`, `include_archived`, `app_id`, `case_id`,
and `order_by` accepting `indexed_on`, `server_modified_on`, or `received_on`.

Note the reST table lists `indexed_on`, `server_modified_on`, and
`received_on` as if they were parameter names, but their example column
shows `order_by=<value>`. They are **values of `order_by`**, not
parameters. Model `order_by` as an enum and record this as a doc
discrepancy.

**Form response schema:** the sample at `list-forms.rst:84-140` shows the
`form` field is the arbitrary, application-specific XForm instance as JSON.
Type it `type: object, additionalProperties: true` with a description
saying the shape depends on the application's form definition. Do not
attempt to model it.

**Submission operations** — opaque bodies per the design:
- `submitForm` accepts two content types, both documented:
  `multipart/form-data` with an `xml_submission_file` part
  (`form-submission.rst:22`), and a raw `application/xml` body
  (`form-submission.rst:41`). Declare both under `requestBody.content`.
- Response is OpenRosa XML: `text/xml` with `type: string`, plus a
  description linking to
  `https://bitbucket.org/javarosa/javarosa/wiki/FormSubmissionAPI`.
- Read `form-submission.rst:150-357` for the documented status codes and
  the `X-OpenRosa-Version` header; include the header as a parameter.
- `tags: [Submission]` for both submission operations.

- [ ] **Step 1: Read the source** — `list-forms.rst`, `form-data.rst`, and `form-submission.rst` in full, then `corehq/apps/api/resources/v0_4.py:64-185`, `corehq/apps/api/object_fetch_api.py`, and `corehq/apps/receiverwrapper/urls.py`.
- [ ] **Step 2: Write** `docs/api/openapi/components/schemas/form.yaml`, with the `form` field typed as an open object as noted above.
- [ ] **Step 3: Write** `docs/api/openapi/paths/form.yaml` (`tags: [Data]`) and `docs/api/openapi/paths/submission.yaml` (`tags: [Submission]`), modelling `order_by` as an enum and both submission content types.
- [ ] **Step 4: Add** the five `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. The `receiver/` paths are outside `api/` — a resolution failure means the urlconf differs from the doc.

- [ ] **Step 7: Record discrepancies and commit** — including the `order_by` table mislabelling noted above.

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add form data and form submission endpoints"
```

---

### Task 11: Mobile workers and web users

**Files:**
- Create: `docs/api/openapi/paths/user.yaml`, `docs/api/openapi/paths/web-user.yaml`, `docs/api/openapi/components/schemas/user.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: components from Task 2.
- Produces: `components/schemas/user.yaml#/MobileWorker`, `#/WebUser`.

**Source:** `docs/api/list-mobile-workers.rst` (212), `docs/api/mobile-worker.rst`
(313), `docs/api/list-webusers.rst` (144), `docs/api/webuser.rst` (361).
Code: `corehq/apps/api/resources/v0_1.py:25-165`,
`v0_5.py:241-330` (mobile), `v0_5.py:473-500` (web),
`v1_0.py:76-120` (invitation), `v0_5.py:1145-1165` (identity).

**Paths:**
- `/a/{domain}/api/user/v1/` GET, POST — `listMobileWorkers`, `createMobileWorker`
- `/a/{domain}/api/user/v1/{user_id}/` GET, PUT, DELETE — `getMobileWorker`, `updateMobileWorker`, `deleteMobileWorker`
- `/a/{domain}/api/user/v1/{user_id}/email_password_reset/` POST — `sendMobileWorkerPasswordReset` (`mobile-worker.rst:297`)
- `/a/{domain}/api/web-user/v1/` GET — `listWebUsers`
- `/a/{domain}/api/web-user/v1/{user_id}/` GET, PATCH — `getWebUser`, `updateWebUser`
- `/a/{domain}/api/invitation/v1/` POST — `inviteWebUser`
- `/api/identity/v1/` GET — `getIdentity` (**no `{domain}`** — mounted at root via `urls.py:108`)

**`listMobileWorkers` query parameters** (`list-mobile-workers.rst:43-52`):
`format`, `group`, `archived`, `extras`, plus `limit`/`offset`.
**`listWebUsers`** (`list-webusers.rst:39`): `web_username`, plus `limit`/`offset`.

**Response fields:** mobile worker at `list-mobile-workers.rst:64-94`
(`id`, `username`, `first_name`, `last_name`, `default_phone_number`,
`email`, `phone_numbers`, `groups`, `primary_location`, `locations`,
`user_data`); web user at `list-webusers.rst:51-78` (`id`, `username`,
`first_name`, `last_name`, `default_phone_number`, `email`,
`phone_numbers`, `role`, `permissions`, `is_admin`). Cross-check the web
user fields against the extra fields declared at `v0_5.py:474-481`
(`primary_location_id`, `assigned_location_ids`, `profile`, `user_data`,
`tableau_role`, `is_active_in_domain`, `tableau_groups`) — several look
undocumented.

**Resolve the flagged discrepancy:** `webuser.rst` documents
`POST /api/web-user/v1/`, `.../activate/`, and `.../deactivate/`, but
`v0_5.WebUserResource.Meta` declares only `detail_allowed_methods =
['get', 'patch']` and inherits `list_allowed_methods = ['get']`. Search for
the activate/deactivate views (`grep -rn "activate" corehq/apps/users/`),
and include them only if they exist and resolve. Whatever you find, record
it in the discrepancy file — this is the single most likely place the docs
are wrong.

- [ ] **Step 1: Read the source** — all four reST docs in full, then `v0_1.py:25-165`, `v0_5.py:241-330`, `v0_5.py:473-500`, `v1_0.py:76-120`, `v0_5.py:1145-1165`.
- [ ] **Step 2: Write** `docs/api/openapi/components/schemas/user.yaml` with `MobileWorker`, `MobileWorkerList`, `MobileWorkerWrite`, `WebUser`, `WebUserList`, and `Invitation`.
- [ ] **Step 3: Write** `docs/api/openapi/paths/user.yaml` and `docs/api/openapi/paths/web-user.yaml`, `tags: [Users]`. Remember `/api/identity/v1/` has **no** `{domain}` parameter.
- [ ] **Step 4: Add** the seven `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. `/api/identity/v1/` is root-mounted — if it fails to resolve, check `urls.py:108` rather than assuming a typo.

- [ ] **Step 7: Record discrepancies and commit** — including the activate/deactivate finding and any undocumented web user fields.

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add mobile worker and web user resources"
```

---

### Task 12: Bulk user, SSO, and user domains

**Files:**
- Create: `docs/api/openapi/paths/bulk-user.yaml`, `docs/api/openapi/paths/sso.yaml`, `docs/api/openapi/paths/user-domains.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: `components/schemas/user.yaml` from Task 11.
- Produces: nothing later tasks depend on.

**Source:** `docs/api/bulk-user.rst` (91), `docs/api/sso.rst` (26),
`docs/api/user-domain-list.rst` (51). Code: `v0_5.py:172-240` (bulk user),
`v0_4.py:260-310` (SSO), `v0_5.py:1091-1144` (user domains).

**Paths:**
- `/a/{domain}/api/bulk-user/v1/` GET — `listUsersBulk`. Params documented at `bulk-user.rst:72-85`; response fields at `:23-33`.
- `/a/{domain}/api/sso/v1/` POST — `authenticateUser`. **List endpoint only** — `v0_4.SingleSignOnResource.Meta` sets `detail_allowed_methods = []`.
- `/api/user_domains/v1/` GET — `listUserDomains`. **No `{domain}`** — root-mounted.

**SSO needs two unusual things:**
1. `security: []` on the operation — credentials go in the body, not a
   header. This is the one endpoint that overrides the global security.
2. `requestBody` with content type
   `application/x-www-form-urlencoded`, schema with required `username` and
   `password` string properties (`sso.rst:20-23`).
   `sso.rst:25` says the response is identical to the mobile worker or web
   user detail response, so `$ref` those schemas from Task 11 in a `oneOf`.

- [ ] **Step 1: Read the source** — `bulk-user.rst`, `sso.rst`, `user-domain-list.rst` in full, then `v0_5.py:172-240`, `v0_4.py:260-310`, `v0_5.py:1091-1144`.
- [ ] **Step 2: Write** any schemas these need, reusing `components/schemas/user.yaml` from Task 11 for the SSO response.
- [ ] **Step 3: Write** `paths/bulk-user.yaml`, `paths/sso.yaml`, `paths/user-domains.yaml`, `tags: [Users]`. SSO gets `security: []` and a urlencoded request body.
- [ ] **Step 4: Add** the three `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. `/api/user_domains/v1/` is root-mounted, like identity in Task 11.

- [ ] **Step 7: Record discrepancies and commit**

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add bulk user, SSO, and user domains endpoints"
```

---

### Task 13: Locations and location types

**Files:**
- Create: `docs/api/openapi/paths/location-v1.yaml`, `docs/api/openapi/paths/location-v2.yaml`, `docs/api/openapi/paths/location-type.yaml`, `docs/api/openapi/components/schemas/location.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: components from Task 2.
- Produces: nothing later tasks depend on.

**Source:** `docs/api/locations-v1.rst` (89), `docs/api/locations-v2.rst` (257),
`docs/api/location-types.rst` (73). Code:
`corehq/apps/locations/resources/v0_5.py`, `v0_6.py`.

**Paths and methods** (note v1 and v2 differ sharply):
- `/a/{domain}/api/location/v1/` GET; `.../{location_id}/` GET — `v0_5.LocationResource` declares `allowed_methods = ['get']`
- `/a/{domain}/api/location/v2/` GET, POST, PATCH; `.../{location_id}/` GET, PUT — `v0_6.LocationResource` declares `list_allowed_methods = ['get', 'post', 'patch']`, `detail_allowed_methods = ['get', 'put']`
- `/a/{domain}/api/location_type/v1/` GET; `.../{id}/` GET

**v1 response fields** (`locations-v1.rst:51-61`): `site_code`,
`external_id`, `created_at`, `last_modified`, `latitude`, `longitude`.

**v2 filter parameters** (`locations-v2.rst:52-76`): `format`, `site_code`,
`name`, `location_type_code`, `parent_location_id`, and the four
`last_modified.gte` / `.gt` / `.lt` / `.lte` range filters. The dotted
parameter names are literal query-string keys — quote them in YAML.

**v2 write payload** (`locations-v2.rst:136-144` for create,
`:182-194` for update): `name`, `site_code`, `latitude`, `longitude`,
`location_data`, `location_type_code`, `parent_location_id`. Create and
update differ — read both blocks and write two schemas rather than reusing
one.

**Location type response** (`location-types.rst:24-42`): `administrative`,
`code`, `domain`, `id`, `name`, `parent`, `resource_uri`, `shares_cases`,
`view_descendants`. Note `id` is an **integer** here, unlike the UUID
string ids elsewhere.

- [ ] **Step 1: Read the source** — all three reST docs in full, then `corehq/apps/locations/resources/v0_5.py` and `v0_6.py`.
- [ ] **Step 2: Write** `docs/api/openapi/components/schemas/location.yaml` with `Location`, `LocationList`, `LocationCreate`, `LocationUpdate`, `LocationType`, `LocationTypeList` — two distinct write schemas, per the note above.
- [ ] **Step 3: Write** `paths/location-v1.yaml` (GET only), `paths/location-v2.yaml` (GET/POST/PATCH list, GET/PUT detail), `paths/location-type.yaml` (GET only), `tags: [Data]`. Quote the dotted `last_modified.gte`-style parameter names.
- [ ] **Step 4: Add** the six `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. `location_type` detail uses an integer id — give its `example` an integer-shaped value.

- [ ] **Step 7: Record discrepancies and commit**

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add location and location type resources"
```

---

### Task 14: Fixtures and lookup tables

**Files:**
- Create: `docs/api/openapi/paths/fixture.yaml`, `docs/api/openapi/paths/lookup-table.yaml`, `docs/api/openapi/components/schemas/lookup-table.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: components from Task 2.
- Produces: nothing later tasks depend on.

**Source:** `docs/api/fixture.rst` (463 lines — covers three resources plus
an async upload). Code: `corehq/apps/fixtures/resources/v0_1.py`,
`corehq/apps/fixtures/views.py`.

The doc has three top-level sections; read each before writing:
- `fixture.rst:1-99` — the read-only fixture API
- `fixture.rst:100-178` — the Excel upload API and its status endpoint
- `fixture.rst:179-463` — the lookup table and lookup table item APIs

**Paths:**
- `/a/{domain}/api/fixture/v1/` GET; `.../{fixture_item_id}/` GET — `listFixtures`, `getFixture`. Query param `fixture_type` (`fixture.rst:42-52`).
- `/a/{domain}/api/lookup_table/v1/` GET, POST; `.../{lookup_table_id}/` GET, PUT, DELETE
- `/a/{domain}/api/lookup_table_item/v1/` GET, POST; `.../{lookup_table_item_id}/` GET, PUT, DELETE
- `/a/{domain}/fixtures/fixapi/` POST — `uploadFixtureExcel`. `multipart/form-data`, opaque `.xlsx` body (`type: string, format: binary`). Params at `fixture.rst:128-145`.
- `/a/{domain}/fixtures/fixapi/status/{download_id}/` GET — `getFixtureUploadStatus` (`fixture.rst:249`).

**Watch for:** `fixtures/v0_6.LookupTableItemResource` is registered at
`v2` (`urls.py:193`) but `fixture.rst` documents only `v1`. Since the spec
covers what the docs cover, leave `v2` out — and record the undocumented
`v2` endpoint in the discrepancy file.

- [ ] **Step 1: Read the source** — all three sections of `fixture.rst` as delimited above, then `corehq/apps/fixtures/resources/v0_1.py` and `corehq/apps/fixtures/views.py`.
- [ ] **Step 2: Write** `docs/api/openapi/components/schemas/lookup-table.yaml` with the fixture, lookup table, and lookup table item schemas plus their list envelopes and write payloads.
- [ ] **Step 3: Write** `paths/fixture.yaml` and `paths/lookup-table.yaml`, `tags: [Data]`. The `fixapi` upload uses `multipart/form-data` with `type: string, format: binary`.
- [ ] **Step 4: Add** the eight `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. The `/fixtures/fixapi/` paths sit outside `api/` — verify against `corehq/apps/fixtures/urls.py` if resolution fails.

- [ ] **Step 7: Record discrepancies and commit** — including the undocumented `lookup_table_item/v2`.

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add fixture and lookup table resources"
```

---

### Task 15: Reports, DET exports, and applications

**Files:**
- Create: `docs/api/openapi/paths/report.yaml`, `docs/api/openapi/paths/det-export.yaml`, `docs/api/openapi/paths/application.yaml`, and matching schema files
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: components from Task 2.
- Produces: nothing later tasks depend on.

**Source:** `docs/api/list-reports.rst` (119), `docs/api/download-report-data.rst`
(100), `docs/api/det-exports.rst` (84), `docs/api/application-structure.rst`
(108), `docs/api/import-app.rst` (298), `docs/api/bulk-upload-cases.rst` (134).

**Paths:**
- `/a/{domain}/api/simplereportconfiguration/v1/` GET; `.../{report_id}/` GET — `listReports`, `getReport`. Output fields at `list-reports.rst:22-40`.
- `/a/{domain}/api/configurablereportdata/v1/{report_id}/` GET — `downloadReportData`. **Detail only** — `v0_5.ConfigurableReportDataResource` declares `list_allowed_methods = []`, so do not add a list path. Params `offset`, `limit`, and arbitrary `filter_name` keys (`download-report-data.rst:38-44`); model the arbitrary filters with a description, since OpenAPI cannot express free-form query keys — note this limitation in the operation description for agent consumers.
- `/a/{domain}/api/det_export_instance/v1/` GET — `listDETExports`. Response fields described prose-style at `det-exports.rst:20-55`; example at `:59-84`.
- `/a/{domain}/api/application/v1/` GET; `.../{app_id}/` GET — `listApplications`, `getApplication`. Sample output at `application-structure.rst:47`.
- `/a/{domain}/apps/api/import_app/` POST — `importApplication`. Opaque JSON app-source body; params at `import-app.rst:47-66`; 201 response at `:78`; update behaviour and 200 response at `:99-123`; documented error responses at `:124-143`.
- `/a/{domain}/apps/api/{app_id}/multimedia/` POST — `uploadApplicationMultimedia`. Params at `import-app.rst:161-172`.
- `/a/{domain}/apps/api/{app_id}/multimedia/status/{processing_id}/` GET — `getMultimediaUploadStatus`. Two documented 200 shapes (in-progress at `:235`, complete at `:255`) — model with `oneOf`.
- `/a/{domain}/importer/excel/bulk_upload_api/` POST — `bulkUploadCases`. `multipart/form-data` with an opaque Excel file; params at `bulk-upload-cases.rst:28-69`; response at `:87`.

**Confirm the non-`api/` paths against code before writing them:**
`grep -rn "import_app\|multimedia" corehq/apps/app_manager/urls.py` and
`grep -rn "bulk_upload_api" corehq/apps/case_importer/urls.py`. The Task 4
resolution test will catch mistakes, but reading the urlconf first is faster
than iterating.

- [ ] **Step 1: Read the source** — all six reST docs in full, then `v0_5.py:812-1003`, `v1_0.py:177-210`, `v0_4.py:312-340`, plus the app_manager and case_importer urlconfs.
- [ ] **Step 2: Write** the schema files for reports, DET exports, applications, and the import/upload status responses (the multimedia status needs a `oneOf` over its two documented 200 shapes).
- [ ] **Step 3: Write** `paths/report.yaml`, `paths/det-export.yaml`, `paths/application.yaml`, `tags: [Data]`. No list path for `configurablereportdata` — detail only.
- [ ] **Step 4: Add** the ten `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. Four of these paths are outside `api/` — confirm them against the urlconfs as noted above.

- [ ] **Step 7: Record discrepancies and commit**

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add report, DET export, and application endpoints"
```

---

### Task 16: Messaging events

**Files:**
- Create: `docs/api/openapi/paths/messaging-event.yaml`, `docs/api/openapi/components/schemas/messaging-event.yaml`
- Modify: `docs/api/openapi/openapi.yaml`, `docs/api/openapi/dist/*`

**Interfaces:**
- Consumes: `components/schemas/pagination.yaml#/CursorMeta` from Task 2.
- Produces: nothing later tasks depend on.

**Source:** `docs/api/messaging-events.rst` (325). Code:
`corehq/apps/api/resources/messaging_event/view.py`, `urls.py:138-142`.

**Paths:** `/a/{domain}/api/messaging-event/v1/` GET — `listMessagingEvents`;
`/a/{domain}/api/messaging-event/v1/{event_id}/` GET — `getMessagingEvent`.

**This is the one endpoint that uses `CursorMeta`, not `PaginationMeta`.**
Its list response must reference `CursorMeta`. Read
`messaging-events.rst:114-142` for the cursor semantics and state in the
`cursor` parameter description that the value is opaque and must be taken
from the previous response's `next` link, never constructed.

**Filters** are documented prose-style at `messaging-events.rst:31-113`
rather than in a table — read that whole range and enumerate them. The
examples at `:197-220` show `content_type`, `phone_number`, `date.gte`,
and `cursor`. Dotted range filters (`date.gte`, `date.lte`) follow the same
pattern as locations v2 in Task 13.

`tags: [SMS]`.

- [ ] **Step 1: Read the source** — `messaging-events.rst` in full, especially the prose filter section at lines 31-113, then `corehq/apps/api/resources/messaging_event/view.py` and `urls.py:138-142`.
- [ ] **Step 2: Write** `docs/api/openapi/components/schemas/messaging-event.yaml`; its list envelope references `pagination.yaml#/CursorMeta`, **not** `PaginationMeta`.
- [ ] **Step 3: Write** `docs/api/openapi/paths/messaging-event.yaml`, `tags: [SMS]`, with the full enumerated filter set and the opaque-cursor warning in the `cursor` parameter description.
- [ ] **Step 4: Add** the two `$ref` entries to `openapi.yaml`.
- [ ] **Step 5: Regenerate** — `yarn openapi:bundle && yarn openapi:docs`
- [ ] **Step 6: Run the full gate**

```bash
yarn openapi:lint && yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
```

Expected: all pass. `{event_id}` is a numeric id (`\d+` in the urlconf) — its `example` must be digits only.

- [ ] **Step 7: Record discrepancies and commit**

```bash
npx prettier --write docs/api/openapi/
git add docs/api/openapi/ docs/superpowers/specs/2026-08-17-openapi-discrepancies.md
git commit -m "feat(openapi): add messaging events endpoints"
```

---

### Task 17: Finalise the discrepancy report and README

**Files:**
- Modify: `docs/superpowers/specs/2026-08-17-openapi-discrepancies.md`
- Modify: `docs/api/openapi/README.md`

**Interfaces:**
- Consumes: discrepancy notes appended by Tasks 3, 8–16.
- Produces: the final triage document.

- [ ] **Step 1: Consolidate the discrepancy report**

Read the accumulated file. Add a summary section at the top:

```markdown
## Summary

- **Total findings:** N
- **Undocumented endpoints or methods:** N
- **Documented but not served:** N
- **Field or parameter mismatches:** N

Findings are grouped by resource below. Each states what the docs say, what
the code does, and which the spec followed (always the code).
```

Then verify every finding still names a real file, class, and line. Delete
any finding you cannot reproduce — an unreproducible finding wastes the
reader's time more than a missing one.

- [ ] **Step 2: Confirm coverage**

Check every scoped reST doc is represented in the spec:

```bash
yarn openapi:bundle
grep -c '^  /' docs/api/openapi/dist/openapi.bundled.yaml
```

Then list the spec's paths and compare against the inventory table in this
plan. Every row must be present except the deliberately excluded
`ota-api-restore.rst`. Record any gap as a finding rather than quietly
leaving it out.

- [ ] **Step 3: Update the README with coverage and known gaps**

Append to `docs/api/openapi/README.md`:

```markdown
## Coverage

Covers the API pages under `docs/api/` except `ota-api-restore.rst`
(opaque, application-specific CaseXML). Admin and internal APIs
(`ADMIN_API_LIST` in `corehq/apps/api/urls.py`) are out of scope.

Some request and response bodies are intentionally opaque — form
submission, app import, and Excel upload payloads are typed as strings
with descriptions, because OpenAPI models XML and binary spreadsheet
formats poorly and the contents are application-specific.

Where the reST docs and the serving code disagreed, this spec follows the
code. See `docs/superpowers/specs/2026-08-17-openapi-discrepancies.md`.
```

- [ ] **Step 4: Run the complete gate one final time**

```bash
yarn openapi:lint
yarn openapi:check
uv run pytest --reusedb=1 corehq/apps/api/tests/test_openapi_spec.py -v
rm -rf docs/_build && ./scripts/test-make-docs.sh
```

All four must pass. Report the actual output — do not claim success without
it.

- [ ] **Step 5: Commit**

```bash
npx prettier --write docs/superpowers/specs/2026-08-17-openapi-discrepancies.md docs/api/openapi/README.md
git add docs/superpowers/specs/2026-08-17-openapi-discrepancies.md docs/api/openapi/README.md
git commit -m "docs(openapi): finalise cross-check findings and coverage notes"
```

---

## Notes for the executor

- **The reST docs are the starting point, the code is the authority.** When
  they conflict, the spec follows the code and the conflict is recorded. Do
  not edit `docs/api/*.rst` in this work.
- **Do not invent fields.** If a response field's type is not evident from
  the sample output or the resource's field declarations, use the loosest
  honest type and say so in the `description`. A wrong `format: date-time`
  is worse than a plain `string`.
- **Regenerate `dist/` in the same commit as any source change.** CI fails
  otherwise. On a merge conflict in `dist/`, take either side and rebuild.
- **The URL-resolution test is the safety net.** If it fails, the path
  string is wrong — fix the spec, never the test.
- **Task 9 (cases v2) is roughly as large as tasks 8, 12, and 16 combined.**
  Do not batch it with anything else.
