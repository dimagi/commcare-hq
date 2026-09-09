# QA notes: OpenAPI specs for the CommCare data APIs

Branch: `nh/openapi-specs-groom` (stacked on `nh/api-test-isolation-fixes`)

## What changed

The data APIs now have OpenAPI 3.0.3 specifications generated from the API code
itself, committed under `docs/api/spec/`. The per-endpoint documentation pages
under `docs/api/` no longer hold hand-written parameter and field tables — they
render from those specs instead. So there are two things to look at: the specs,
and the pages built from them.

Nothing about the APIs' behaviour changed. If a request or response behaves
differently from before, that is a bug worth reporting.

## Look at a spec in a browser

The quickest check. Builds one self-contained HTML file — no server, no network
once the tool is fetched:

```bash
npx --yes @redocly/cli build-docs docs/api/spec/user-v1.json -o /tmp/user-v1.html
xdg-open /tmp/user-v1.html
```

Swap in any file from `docs/api/spec/`. Use `bundle.json` to see every
documented endpoint in one page.

## Look at the published documentation pages

This is what readthedocs will show:

```bash
cd docs && uv run make html
xdg-open _build/html/api/list-mobile-workers.html
```

The build takes a few minutes because it imports all of CommCare HQ. Output
lands in `docs/_build/html/`; `api/index.html` is the contents page.

Pages that changed:

`cases-v1`, `cases-v2`, `fixture`, `form-data`, `index`, `list-forms`,
`list-groups`, `list-mobile-workers`, `location-types`, `locations-v1`,
`locations-v2`, `mobile-worker`, `user-group`.

## What to check

On a rendered page, for each endpoint:

- The **HTTP methods** listed are the ones the endpoint really supports.
- **Query parameters** appear with descriptions, and they work when you try them
  against a real server.
- **Response fields** appear with a type and a description, and match what the
  API actually returns.
- **Request bodies** list the fields the endpoint accepts on write — sending one
  should not come back 400 "unknown or non-editable field".
- The **example** payload matches the schema next to it.
- The **permission** sentence names the permission the endpoint really needs.

The most valuable QA here is comparing a page against a real call. If the
documentation promises a parameter, a field or a status code the server does not
deliver, that is exactly the class of bug this work is meant to eliminate —
please report it with the endpoint and the payload.

Three pages are deliberately short pointers to a fuller page, because the
renderer publishes a whole spec at once and putting it on both pages would
collide:

| Pointer page    | Renders the endpoints |
| --------------- | --------------------- |
| `mobile-worker` | `list-mobile-workers` |
| `form-data`     | `list-forms`          |
| `list-groups`   | `user-group`          |

A pointer page with a working link is correct, not a missing page.

## Confirm the specs match the code

```bash
uv run ./manage.py generate_openapi --check     # "OpenAPI specs are up to date."
```

If that reports drift, the committed specs disagree with the code — a real
problem. `uv run ./manage.py generate_openapi` regenerates them.

## Known gaps — please do not file these

- **Field lists show only the first variant** where a request body accepts more
  than one shape (Case API v2's bulk and external-ID bodies). The rendered
  example still shows every shape. This is a limitation of the renderer.
- **Some specs have no field descriptions yet.** Fully described: `case-v1`,
  `form-v1`, `group-v1`, `location-v1`, `location-v2`, `location-type-v1`,
  `lookup-table-v1`, `lookup-table-item-v1`, `lookup-table-item-v2`, `user-v1`,
  and Case API v2. Structurally correct but not yet described: `application-v1`,
  `bulk-user-v1`, `det-export-v1`, `fixture-v1`, `report-config-v1`,
  `report-data-v1`, `sso-v1`, `user-domains-v1`, and `web-user-v1`'s own
  (non-inherited) fields. That is the planned first slice, not an oversight.
- **The lint pass reports 14 warnings**, all `operation-description`, on the
  specs above. Zero errors is the bar; the warning count should fall as those
  APIs are documented.
- **Live-response checking covers `user-v1` and `group-v1` only** in the
  automated tests. Everything else relies on checked-in examples, so manual
  comparison against real calls is worth more on the other APIs.

## Fuller background

- Decisions, follow-ups and known limitations:
  `docs/superpowers/2026-08-18-api-openapi-handover.md`
- How to regenerate and how to document another API:
  `corehq/apps/api/openapi/README.md`
