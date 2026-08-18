# CommCare HQ OpenAPI specification

Machine-readable description of the public APIs documented in `docs/api/`. The
reST pages remain the prose narrative; this spec is the reference.

## Layout

- `openapi.yaml` — root document; `paths` are `$ref`s only
- `paths/` — one file per resource
- `components/` — shared security schemes, parameters, responses, schemas
- `dist/` — **generated, committed** artifacts
  ```
  dist/
    openapi.bundled.yaml   # generated, committed
    openapi/index.html     # generated, committed (Redoc page)
  ```

## Requirements

`@redocly/cli`'s declared supported range is `>=22.12.0 || >=20.19.0 <21.0.0`.
CI pins Node 24 (see `.github/workflows/lint.yml`). Older 20.x releases (below
20.19.0, e.g. 20.7.0) emit an engine-mismatch warning from `yarn`/`npm` but the
tool still runs correctly — `yarn openapi:lint` and friends exit 0. Node 18 and
earlier are genuinely unsupported.

## Working on the spec

    yarn openapi:lint     # validate
    yarn openapi:bundle   # regenerate dist/openapi.bundled.yaml
    yarn openapi:docs     # regenerate dist/openapi/index.html
    yarn openapi:check    # verify dist/ matches source (what CI runs)

Always regenerate `dist/` in the same commit as a source change — CI fails
otherwise.

## Why dist/ is committed

readthedocs builds this repo with a Python-only environment
(`.readthedocs.yml`), so it cannot run the Node bundler. CI regenerates and
diffs the artifacts to guarantee they are current.

**On a merge conflict in `dist/`, do not hand-merge.** Take either side, then
run `yarn openapi:bundle && yarn openapi:docs` and commit the result.

## Scope

The OTA restore API is intentionally excluded: it returns opaque,
application-specific CaseXML. Admin and internal APIs are also excluded.

## Coverage

Covers the API pages under `docs/api/` except `ota-api-restore.rst` (opaque,
application-specific CaseXML). Admin and internal APIs (`ADMIN_API_LIST` in
`corehq/apps/api/urls.py`) are out of scope.

That is 25 of the 26 content pages, across 10 path files and 54 paths — more
paths than reST pages, because several resources serve detail endpoints or
sub-actions the prose docs never mention. Those extras are documented because
the code allows them, and each is recorded as a finding: mobile-worker and
web-user `activate`/`deactivate`, the DET export detail endpoint, and the detail
endpoints of `location/v1`, `location/v2`, `location_type/v1`, `fixture/v1`,
`lookup_table/v1`, `lookup_table_item/v1` and `simplereportconfiguration/v1`.

Some request and response bodies are intentionally opaque — form submission, app
import, and Excel upload payloads are typed as strings with descriptions,
because OpenAPI models XML and binary spreadsheet formats poorly and the
contents are application-specific.

Where the reST docs and the serving code disagreed, this spec follows the code.
See `docs/superpowers/specs/2026-08-17-openapi-discrepancies.md`.

## Known gaps

- **Operations the code rejects are not published.** Where a method resolves but
  can only ever fail — `POST` to the by-external-id case path, writes to
  `location_type/v1` and `fixture/v1` — the operation is omitted and an inline
  YAML comment says why, so a later pass does not "fix" it back in.
- **Responses the code cannot produce are not declared.** Several detail
  operations omit `404` because the underlying lookup raises an exception
  tastypie does not map to one (`replaceGroup`, `updateMobileWorker`,
  `replaceLocationV2`). Each carries an inline comment.
- **Error bodies vary far more than the shared components suggest.** The shared
  `Unauthorized`, `Forbidden` and `NotFound` responses each carry a warning
  comment: their JSON body is real but not universal, and several resources
  return an empty body or a Django HTML error page instead. Verify the actual
  shape before pointing a new operation at a shared ref.
- **Not exercised against a running server.** The spec is a static trace of the
  source. Findings that would need a live Postgres, Elasticsearch or Celery
  worker to confirm are flagged as such in the discrepancy file.
- **`lookup_table_item/v2` is registered but undocumented** by `fixture.rst`, so
  it is out of scope here; see the discrepancy file.
