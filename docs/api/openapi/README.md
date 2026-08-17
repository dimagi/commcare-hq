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

`@redocly/cli` requires Node 24 (the version this repo's CI uses — see
`.github/workflows/lint.yml`). Node 20 cannot run it. If `yarn openapi:lint`
fails to start, check your Node version first.

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
