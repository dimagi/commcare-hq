# API reference pages and OpenAPI discovery endpoints

Date: 2026-08-20 Builds on: `nh/openapi-specs-groom` Preceding design:
`docs/superpowers/specs/2026-08-17-commcare-api-openapi-design.md`

## Purpose

The generated OpenAPI specs are correct but hard to read. They are published
today as reStructuredText rendered by `sphinxcontrib-openapi`, which lists
endpoints and fields but reads like reference material rather than an API
console. This work publishes a Redoc reference page per documented API, and
serves the specs at stable URLs so that agents and tooling can find them.

Two consumers, and they want different things:

- **Humans** want a browsable page per API, with the endpoints, the fields and
  their descriptions, and an example payload — the shape of documentation an
  integrator expects in 2026.
- **Agents and MCP tooling** want the machine-readable document at a predictable
  URL, describing the instance that served it.

## Non-goals

- Documenting error responses. That is a separate design
  (`2026-08-20-api-error-responses-design.md`) and lands after this.
- Reducing the reStructuredText pages. Also separate
  (`2026-08-20-api-rst-reduction-design.md`), and dependent on this and on the
  error-response work.
- Extending spec coverage to the APIs the generator does not yet reach (OpenRosa
  submission, messaging-event, bulk case upload). Follow-up.
- Authentication on any of these endpoints. The same content is already
  published publicly; see Security below.

## Decisions

**Redoc pages are built during the asset build and served as static files, not
committed.** `redocly build-docs` runs per spec alongside `yarn build`,
producing roughly 20 pages of about 160KB each. Rejected: committing the built
HTML with a freshness gate, as the `ce/openapi-spec` branch did — that branch
had to, because readthedocs builds Python-only and cannot run Node, whereas we
serve from Django where the asset pipeline already runs. Committing generated
HTML would add roughly 3MB to the repository with none of the reviewability that
justifies committing the specs themselves. Also rejected: mounting Redoc through
webpack as a JS entry point, which would keep the page always in sync with the
spec but makes its content invisible to grep and to anything reading the HTML
without executing JavaScript — the wrong trade when agents are a stated
audience.

This is safe to rely on in deployed environments: building and deploying static
assets is a required deploy step, and an environment that skipped it would have
problems far larger than missing API documentation. The realistic gap is a local
development checkout that has not run the build.

So the missing-artifact path is treated as a development aid rather than a
production concern. The view returns 404 either way; under `settings.DEBUG` the
body names the command that produces the page, and outside `DEBUG` it logs a
warning, because a missing artifact in a deployed environment means the deploy
is broken and should be visible in logs rather than silently absent.
`DEV_SETUP.md` gains a line telling developers that the API reference needs a
static asset build, and needs rebuilding after a spec change.

**One page per API, not one page for the bundle.** Digestibility is the point of
this work; a single page covering twenty APIs reproduces the problem it is meant
to solve. The bundle remains as a machine-readable document.

**The served spec describes the instance serving it.** `servers` is currently
`https://{host}` with `host` defaulting to `www.commcarehq.org`. An agent that
fetches the spec from a self-hosted deployment and follows that default would
send requests to the wrong installation. The spec view substitutes the
requesting host as the default. Rejected: serving the file byte-for-byte as
committed, which is simpler and arguably more honest, but leaves that foot-gun
pointed at exactly the discovery case this work adds.

**URLs live under `/api/`.** `/api/docs/` for the reference and
`/api/openapi.json` for the machine-readable document, which read naturally
beside the `/a/{domain}/api/…` endpoints they describe. Rejected: a separate
`/apidocs/` prefix, as the `ce/openapi-spec` branch used, on the grounds that it
cannot collide with an API resource.

The collision risk that argued for a separate prefix is smaller than it looks.
Almost every resource is domain-scoped and therefore lives under
`/a/{domain}/api/…`, out of reach of these URLs entirely. Root `/api/` is not
empty — `urls.py:108` mounts the user-scoped resources there, so
`/api/identity/v1/` and `/api/user_domains/v1/` exist — but a collision would
require a future _user-scoped_ resource named exactly `docs` or a document named
`openapi.json`. With two user-scoped resources in the catalogue, that is
negligible rather than impossible, and the docs URLs are registered ahead of the
resource include so they resolve first if it ever happens.

**`/.well-known/openapi.json` is a convenience alias, not a standard.** RFC 8615
governs the well-known namespace and there is no IANA registration for
`openapi`. The spec, the code comment and the published documentation must all
describe it as a de facto convention. It is worth adding because it lets a
client that knows only a hostname find the API surface, which is the one thing a
documented URL cannot do.

## Architecture

### URLs

| URL                             | Serves                              |
| ------------------------------- | ----------------------------------- |
| `/api/docs/`                    | index of the documented APIs        |
| `/api/docs/<slug>/`             | Redoc page for one API              |
| `/api/docs/<slug>/openapi.json` | that API's spec, host-substituted   |
| `/api/openapi.json`             | the merged bundle, host-substituted |
| `/.well-known/openapi.json`     | alias for the bundle                |

`<slug>` is the existing `ApiEntry.doc_slug` (`user-v1`, `case-v2`, …), so URLs
map one-to-one onto the committed spec files and no second naming scheme
appears.

A new `corehq/apps/api/docs_urls.py` is included from the project root under
`^api/`, registered **before** the existing user-scoped resource include so the
documentation URLs resolve first. `/.well-known/openapi.json` is its own root
entry pointing at the same view.

### The index page

A Django template rendered from `catalogue.documented_entries()` at request time
— not a generated artifact. It therefore cannot drift from what is actually
documented, and adding an API to the catalogue makes it appear with no build
step.

It also names, per API, whether every field carries a description or whether the
spec is structurally generated but not yet described. That distinction is
currently something a reader has to be told out of band; the index is the
natural place for it, and it makes the remaining documentation work visible
rather than invisible.

### Views

One module, `corehq/apps/api/docs_views.py`, holding three views: the index, the
per-API page, and the spec. Artifacts are read once and cached for the process
lifetime, since they are immutable for the lifetime of a deploy.

The **page view** resolves `<slug>` against the catalogue — an unknown slug is a
404, not a filesystem lookup — then returns the built HTML for it. When the
build has not run, the 404 body names the command that produces the page.

The **spec view** loads the requested document, replaces the `servers` host
default with the requesting host, and adds CORS headers using the existing
`corehq.apps.api.cors.add_cors_headers_to_response`, so that browser-based
tooling on another origin can fetch it. Its ETag derives from both the file's
content hash and the host, because the served bytes differ per host and a
content-only ETag would let a proxy serve one deployment's spec to another.

### Build

Three `package.json` scripts, following `ce/openapi-spec`:

    openapi:lint    redocly lint over the specs
    openapi:bundle  (already covered by generate_openapi; see below)
    openapi:docs    redocly build-docs per spec into the dist directory

`@redocly/cli` becomes a dev dependency. `openapi:docs` iterates the spec files
rather than hard-coding a list, so a new API needs no build change.

We keep `./manage.py generate_openapi` as the only producer of the specs
themselves, including the bundle — Redocly's bundler is not introduced as a
second source of truth for spec content.

## Testing

- The page view returns the built HTML for a known slug; an unknown slug 404s
  without touching the filesystem; a missing artifact 404s with the build
  command in the body. Tests use a fixture artifact, since the Node build does
  not run under pytest.
- The spec view returns valid JSON; its `servers` default equals the request
  host; CORS headers are present; the ETag is stable for repeated requests from
  one host and differs across hosts; the same document is served at the per-API,
  bundle and `.well-known` URLs.
- An anonymous client receives 200 from every one of these endpoints. This is
  asserted explicitly so that the endpoints cannot acquire authentication by
  accident later.
- The index lists every documented entry, and its description-coverage marking
  matches what the specs actually contain — derived from the specs, not
  hard-coded, so it cannot go stale.
- CI gains one step: run `yarn openapi:docs`, failing if Redocly errors. With
  nothing committed there is no drift to check; the real risk is a spec that
  stops rendering, and this catches it.

## Security

Every endpoint is unauthenticated. The specs describe endpoint shapes and carry
no credentials, and the same content is already published on readthedocs, so
gating them would only make the reference harder for integrators to reach while
protecting nothing.

Two risks worth recording. The bundle is roughly 344KB, so the spec endpoints
are a cheap way to pull a moderate payload repeatedly; the process-lifetime
cache avoids re-reading and re-parsing the document from disk, but every hit
still re-serialises and re-transfers the full bundle, and the ETag is inert --
nothing answers `If-None-Match`, and no client or proxy may store the
response -- so a repeat request is not inexpensive. No rate limit is
proposed and that is a deliberate choice to revisit if it is abused. And
`Access-Control-Allow-Origin: *` on the spec endpoints is intentional — the
documents are public — but it should not be extended to any endpoint that
becomes authenticated.

## Risks

- **A developer's first visit to the page may 404.** Deployed environments build
  static assets as a required step, so this is a local-checkout problem, not a
  production one. The `DEBUG`-gated message and the `DEV_SETUP.md` note are the
  mitigation; if developers still trip over it, committing the artifacts with a
  freshness gate is the fallback and needs no design change.
- **A spec change silently stales the page** until assets are rebuilt. The same
  applies to every other static asset in this repo, so it needs no special
  machinery, but it is the reason `DEV_SETUP.md` mentions rebuilding after a
  spec change rather than only at install.
- **Redoc pages are standalone**, so a reader on a per-API page has no link back
  to the index. Accepted rather than solved: the alternatives are
  post-processing generated HTML or an iframe, both worse than the problem.
  Revisit only if readers ask.
- **`/api/docs/` and `/api/openapi.json` are a new public surface** and, once
  integrators bookmark them, the URLs are effectively permanent. They are named
  accordingly.
