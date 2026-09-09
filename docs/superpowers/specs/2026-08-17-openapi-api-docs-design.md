# OpenAPI 3.0 Specification for CommCare HQ Public APIs

**Date:** 2026-08-17
**Status:** Approved design, pending implementation

## Problem

The 25 public APIs documented under `docs/api/` exist only as hand-written
reST prose. Nothing about them is machine-readable, which blocks two
things we want:

1. **LLM and agent tooling.** Converting an OpenAPI document into tool
   definitions is a solved problem; transcribing reST prose into them is
   not, and hand-transcription drifts.
2. **Interactive reference docs.** Integrators currently read prose and
   assemble cURL commands by hand. The docs point them at an external
   API Explorer, which is a separate system with its own lifecycle.

There is no OpenAPI, Swagger, or drf-spectacular infrastructure in the
repository today. The APIs are served mostly by tastypie resources
(`corehq/apps/api/resources/v0_1` through `v1_0`, plus resources in the
`locations`, `fixtures`, and `hqcase` apps), which offer no schema
introspection.

## Goals

- A valid, complete OpenAPI 3.0 document covering the APIs documented in
  `docs/api/`, accurate enough to drive both agent tool definitions and a
  browsable reference.
- Mechanical protection against drift, so the spec fails CI rather than
  quietly becoming wrong.
- A triage list of the places where today's docs disagree with today's
  code.

## Non-goals

- **Replacing the reST docs.** They remain the prose narrative; the spec
  becomes the reference. Consolidating the two is a possible follow-up,
  not part of this work.
- **Generating the spec from code at runtime.** Tastypie has no OpenAPI
  support, and several documented endpoints are not tastypie resources at
  all. A generator is a subsystem in its own right and is out of scope.
- **Modelling XML payload schemas.** OpenAPI models XML poorly, and the
  payloads are application-specific.
- **The OTA restore API.** Excluded by decision: it returns opaque,
  app-specific CaseXML and its documented entry point is a browser flow.

## Scope

`docs/api/` holds 27 reST files: a landing page (`index.rst`) and 26 API
pages. This work covers 25 of those 26 — all but `ota-api-restore.rst` —
yielding roughly 22 path items and 50 operations.

Three documented endpoints are included with **opaque bodies** — full
path, parameter, auth, and status-code coverage, with request and
response bodies typed as `application/xml` or `application/octet-stream`
(`type: string`) plus a description and a link to the governing external
spec:

- `form-submission.rst` — OpenRosa form submission
- `import-app.rst` — app import and multimedia upload
- `bulk-upload-cases.rst` — Excel case upload

## Source of truth

Each reST page is translated to OpenAPI, then **cross-checked against the
code that serves it**: the relevant tastypie resource, and
`corehq/apps/api/urls.py` for the path and version. The four things
checked are path/version, allowed HTTP methods, filterable query
parameters, and response field names.

Where the docs and code disagree, **the spec records what the code
does**, and the disagreement is written to
`docs/superpowers/specs/2026-08-17-openapi-discrepancies.md` for human
triage. Some will be doc bugs worth fixing; others may be deliberate
omissions. The spec never guesses at which.

## Architecture

### File layout

```
docs/api/openapi/
  openapi.yaml            # root: info, servers, security, tags, paths ($refs only)
  redocly.yaml            # linter ruleset
  paths/                  # one file per RESOURCE
  components/
    securitySchemes.yaml
    parameters.yaml
    responses.yaml
    schemas/
  dist/
    openapi.bundled.yaml  # committed build artifact
    index.html            # committed Redoc page
```

Path files are organised **per resource, not per document**. Six reST
pages pair onto three resources, and OpenAPI permits each path to appear
only once:

| Resource | Documented in |
|---|---|
| `/api/group/v1/` | `list-groups.rst`, `user-group.rst` |
| `/api/user/v1/` | `list-mobile-workers.rst`, `mobile-worker.rst` |
| `/api/web-user/v1/` | `list-webusers.rst`, `webuser.rst` |

Conversely, `fixture.rst` documents three resources (`fixture/v1`,
`lookup_table/v1`, `lookup_table_item/v1`) plus an async upload/status
pair, so it fans out across several path files.

### Shared components

- **`PaginatedResponse`** — the `{meta: {limit, next, offset, previous,
  total_count}, objects: [...]}` envelope used by nearly every list
  endpoint. Per-resource variants use `allOf` to narrow `objects`.
  `messaging-event/v1` uses opaque cursor pagination instead and gets its
  own `CursorMeta`.
- **Security schemes** — `ApiKey` (`Authorization: ApiKey <email>:<key>`,
  modelled as `apiKey` in header because it is not a registered HTTP
  scheme), `Basic`, and `OAuth2` bearer, per
  `corehq/apps/domain/auth.py`. Digest and the formplayer HMAC scheme are
  internal and omitted. Applied globally, overridden per operation where
  it differs — notably `/api/sso/v1/`, which takes credentials in the
  request body and therefore declares `security: []`.
- **The `domain` path parameter** — applied where it belongs rather than
  assumed. `/api/user_domains/v1/` and `/api/identity/v1/` are
  account-scoped, not domain-scoped.
- **Error responses** — 400, 401, 403, 404, 429, 500, with the
  `{"error": "..."}` body shape produced by
  `wrap_4xx_errors_for_apis`. The reST docs are largely silent on failure
  modes, so these come from the code. 429 is included because these
  endpoints are rate-limited.

`servers` uses a templated variable so non-production environments are
selectable rather than hardcoded.

### Grouping

Tags mirror the existing categories in `docs/api/index.rst` so Redoc's
navigation matches what integrators already know: `Data`, `Users`,
`Submission`, `SMS`.

### Notable endpoints

- **Case API v2** is the largest single surface: 8 operations from one
  711-line document — list, detail, `ext/{ext_id}`, comma-separated
  multi-fetch, `POST bulk-fetch`, and create/update via `POST`/`PUT`
  where a list payload implies a bulk operation. The comma-separated
  `GET /api/case/v2/<case_id>,<case_id>` form has no clean OpenAPI path
  parameter equivalent; it is modelled as a single parameter with
  `style: simple`, `explode: false`, and an explicit description of the
  semantics, because agents will otherwise get it wrong.
- **Not every documented endpoint lives under `/api/`.** Bulk case upload
  is `/importer/excel/bulk_upload_api/`, app import is
  `/apps/api/import_app/`, fixture upload is `/fixtures/fixapi/`, and
  form submission is `/receiver/api/`. These appear in the spec with
  their real prefixes.

### Conventions for the two consumers

- **`operationId` and `summary` carry the agent-facing contract.**
  Predictable `operationId`s (`listCases`, `getCase`,
  `createMobileWorker`) and a one-line imperative `summary` on every
  operation, because those are the fields tool-definition converters
  surface as the tool name and description. Redoc uses the same fields
  for navigation, so there is no conflict.
- **Prose goes in `description`; sample payloads become named
  `examples`** rather than being flattened into prose.

A separate trimmed "agent bundle" is deliberately not produced — one
bundled document serves both consumers, and a second artifact is a second
thing to keep in sync. If the bundle later proves too large for a tool
context window, splitting by tag is a cheap follow-up.

## Tooling and CI

`@redocly/cli` as a devDependency in `package.json`. It is the only tool
that covers all three jobs — validation, `$ref` bundling, and Redoc HTML
generation — and the repository already uses Node tooling for
docs-adjacent work.

npm scripts:

| Script | Purpose |
|---|---|
| `openapi:lint` | Validate against the pinned ruleset |
| `openapi:bundle` | Emit `dist/openapi.bundled.yaml` |
| `openapi:docs` | Emit `dist/index.html` |
| `openapi:check` | Rebuild to a temp dir, diff against committed `dist/`, fail on difference |

`openapi:check` is the anti-drift mechanism: a spec edit cannot merge
without regenerating the artifacts.

CI adds a `lint-openapi` job to `.github/workflows/lint.yml`, which
already has a Node-based `lint-javascript` job to model.

## Publishing

`docs/conf.py` gains `html_extra_path` so `docs/api/openapi/dist/` is
copied into the built site, linked from `docs/api/index.rst`.

Two constraints drive this:

1. **readthedocs installs no Node.** `.readthedocs.yml` builds with
   `uv sync --group=docs` only, so the Redoc HTML must be a committed
   artifact rather than generated during the RTD build. CI guarantees it
   is current.
2. **The docs build is strict.** `scripts/test-make-docs.sh` fails on any
   un-whitelisted warning. `html_extra_path` copies files without adding
   them to a toctree, so it introduces no warnings — unlike a
   `.. raw:: html` iframe, and Redoc already ships a complete standalone
   page.

## Testing

Tooling level, in CI: `redocly lint` enforces validity, and the `dist/`
diff check enforces freshness.

Repository level, one new module `corehq/apps/api/tests/test_openapi_spec.py`:

- The bundled spec parses and every `$ref` resolves.
- Every `operationId` is unique, and every operation has `summary`,
  `tags`, and at least one response — the fields the agent consumer
  depends on.
- **Every path in the spec resolves against Django's URL resolver**,
  with domain placeholders filled from a fixture domain and resolved via
  `django.urls.resolve`.

The URL-resolution test is the one with real teeth: if an endpoint is
renamed or removed, the spec fails rather than lying to integrators and
agents. It is built first.

## Risks

- **The discrepancy list may be large.** Recent commits ("Correct
  parameter names and values in API docs", "Fix bulk-user API `q`
  parameter being silently ignored") suggest today's docs and code differ
  in more than a couple of places. This is a benefit of the exercise, but
  it means the cross-check phase may surface more work than it resolves.
  Triage is explicitly deferred to a human.
- **Committed build artifacts invite merge conflicts** in
  `dist/openapi.bundled.yaml`. Mitigated by the artifact being
  regenerable: on conflict, rebuild rather than hand-merge. Worth a note
  in the README.
- **A new Node devDependency** adds surface to the JS toolchain for a
  docs concern. Accepted: the alternative Python toolchain cannot render
  docs, so it would require vendoring Redoc's JS anyway.
