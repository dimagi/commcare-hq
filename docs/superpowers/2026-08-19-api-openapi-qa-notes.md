# QA notes: OpenAPI specs for the CommCare data APIs

Branch: `nh/api-docs-consolidation`

## What changed

The data APIs now have OpenAPI 3.0.3 specifications generated from the API code
itself, committed under `docs/api/spec/`. The reference documentation is built
from those specs as Redoc pages, served at `/api/docs/`.

The reStructuredText pages under `docs/api/` are no longer the reference. Eleven
of them have been reduced to a title, a sentence of orientation and a link to
their API's reference page; `docs/api/index.rst` carries a guide to what applies
across all the APIs (authentication, URL structure, versioning, pagination,
throttling). The remaining pages are unchanged, because their APIs have no
generated spec yet.

So there are three things to look at: the specs, the reference pages built from
them, and the reduced reStructuredText pages.

Anything a reduced page used to say should now be either in the spec (and so on
the reference page) or in the guide. Each reduction has an audit trail under
`docs/api/sweep/` listing every item and where it went — if you find something
that looks lost, that is where to check first, and a genuine omission is worth
reporting.

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

The reference is now a set of Redoc pages built from the specs, served at
`/api/docs/`:

```bash
yarn openapi:docs
```

Then run the dev server and visit `/api/docs/` — that is the contents page,
linking to a reference page per API. Also check:

- `/api/openapi.json` returns the merged spec bundle as JSON.
- `/.well-known/openapi.json` returns the same.

## What to check

On a rendered reference page, for each endpoint:

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

The `docs/api/*.rst` pages are now short orientation pages — a sentence or two
and a link to the reference page — rather than the rendered tables they used to
carry. They're still worth a human look: check that each links to the right
reference page.

## Confirm the specs match the code

```bash
uv run ./manage.py generate_openapi --check     # "OpenAPI specs are up to date."
```

If that reports drift, the committed specs disagree with the code — a real
problem. `uv run ./manage.py generate_openapi` regenerates them.

## Known gaps — please do not file these

- **Some specs have no field descriptions yet.** Fully described: `case-v1`,
  `form-v1`, `group-v1`, `location-v1`, `location-v2`, `location-type-v1`,
  `lookup-table-v1`, `lookup-table-item-v1`, `lookup-table-item-v2` and
  `user-v1`. Partly described: `case-v2` (1 field of 19) and `web-user-v1` (8 of
  19). Structurally correct but not described at all: `application-v1`,
  `bulk-user-v1`, `det-export-v1`, `fixture-v1`, `report-config-v1`,
  `report-data-v1`, `sso-v1` and `user-domains-v1`. That is the planned first
  slice, not an oversight. `/api/docs/` states each API's coverage, so it is the
  quickest way to see the current position rather than trusting this list.
- **`case-v2` is the known exception worth naming**, because it is heavily used
  and barely described. Its backfill is outstanding work, and
  `docs/api/cases-v2.rst` is deliberately left as hand-written prose until that
  lands — so it is the one page that has not been reduced.
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
