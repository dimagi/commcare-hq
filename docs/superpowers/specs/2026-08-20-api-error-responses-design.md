# Documenting the CommCare API's error responses

Date: 2026-08-20 Depends on: `2026-08-20-api-docs-pages-design.md` (this lands
after it) Preceding design:
`docs/superpowers/specs/2026-08-17-commcare-api-openapi-design.md`

## Purpose

The generated specs describe only success. Counting the response codes across
all twenty-one committed documents:

    {'200': 48, '201': 9, '202': 8, '204': 7}

No 400, no 401, no 403, no 404, no 429. For a human reading the reference that
is an omission. For a generated client or an agent it is worse: error handling
is most of the code you write against an API, and the spec currently says
nothing about it.

This is not an oversight in the generator so much as a limit of its method. The
generator reads what tastypie _declares_ about a resource. Error bodies are
produced by authentication decorators, exception wrappers, throttles and
Django's own handlers — none of which a resource declares. They have to be
described deliberately.

## The scale of the problem

An independent audit of code against documentation found 121 discrepancies, and
the **largest single category — 42 of them — was error responses**, not the
documented success shapes. That report is not on this branch; read it with:

    git show ce/openapi-spec:docs/superpowers/specs/2026-08-17-openapi-discrepancies.md

That branch is shared and the report is already in use, so it does not need
merging to serve its purpose. The findings this work depends on are extracted
below rather than left behind a reference, with their citations, so that this
design stands on its own.

Its summary sets the scope:

> This API has at least four distinct 404 bodies, three distinct 403 bodies, two
> distinct 401 bodies, and three distinct 400 bodies (`{"error": ...}`,
> `{"error_message": ...}`, and a bare JSON array of strings), reached through
> different tastypie and Django code paths on resources that otherwise look
> identical.

Shapes confirmed directly in this codebase while writing this design:

| Body                                                                          | Status  | Source                                                                              |
| ----------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------- |
| `{"error": "<message>"}`                                                      | 404     | `corehq/apps/api/resources/auth.py:30` — `Http404` carrying a message               |
| `{"error": "not authorized"}`                                                 | **401** | `auth.py:32` — `Http404` with an _empty_ message becomes a 401                      |
| `{"error": "<message>"}`                                                      | 401     | `resources/__init__.py:137` — API blacklist toggle                                  |
| `{"error": "Your current subscription does not have access to this feature"}` | 401     | `resources/__init__.py:149` — missing plan privilege                                |
| `{"error": "Request method not allowed"}`                                     | 405     | `resources/messaging_event/view.py:39`                                              |
| `{"error": "<message>"}`                                                      | 400     | `messaging_event/view.py:41`, and `UserError` in `hqcase/api/`                      |
| empty body                                                                    | 404     | tastypie's own detail miss — asserted in `corehq/apps/api/tests/case_resources.py`  |
| `{"error_message": ..., "traceback": ...}`                                    | 500     | tastypie's unhandled-exception body, observed live from the `.../schema/` endpoints |
| nested `{"error": {...}}`                                                     | varies  | `corehq/apps/api/odata/utils.py:80` — OData's own convention                        |

Two of these deserve emphasis. An `Http404` with an empty message returns
**401**, not 404 — surprising enough that a client written against a reasonable
assumption will mishandle it. And the same status code carries different bodies
on resources that look identical from the outside.

### What the audit establishes beyond that

The table above is what could be found by reading this codebase directly, and it
is materially incomplete. The audit's traces, extracted here, correct it in ways
that change the design.

A warning about its citations. The audit was written against a tree that did not
yet carry this project's `help_text` and `Docs` additions, so its line numbers
into `corehq/apps/api/resources/v0_4.py` and `v0_5.py` no longer resolve — its
`v0_4.py:274-278` is now `754,757`, and its `v0_5.py:435,456,622` is now
`613,634,838`. The citations below are re-derived against this branch and given
by symbol where a symbol exists, because these files are still being edited and
line numbers will keep moving.

**The common 401 has no body at all.** The JSON `{"error": …}` 401 is real but
is only reachable _after_ a successful login. A missing or invalid credential —
by far the more common case — never reaches CommCare's own code: the scheme's
challenge decorator answers first, returning `HttpResponse(status=401)` with a
`WWW-Authenticate` header and no content (`corehq/apps/domain/auth.py:150-152`,
via `_login_or_challenge` at `corehq/apps/domain/decorators.py:281-305`). Digest
and API-key auth behave the same way. A spec that declares only the JSON shape
describes the rarer half of the behaviour.

**The 403 body is empty on most resources**, not the shared JSON shape — the
audit confirms this for group, case v1, case v2, form, location v1 and
location_type. Three resources in that branch's own spec pointed at a shared
JSON `Forbidden` without having checked.

**There are at least four distinct 404 shapes**, and two are not JSON at all:

- tastypie's bare `HttpNotFound()`, empty body (`getCase`, `getForm`)
- `{"error": "<message>"}` from `wrap_4xx_errors_for_apis` when the `Http404`
  carries a message
- Django's **HTML** 404 page, when a bare `Http404` escapes to `handler404` —
  `get_form_attachment_response` (`corehq/apps/reports/views.py:1517-1520`) does
  this for a missing attachment
- tastypie's canned
  `{"error_message": "Sorry, this request could not be processed. Please try again later."}`,
  reached when a `prepend_urls` view raises an argument-less `NotFound()`
  (`v0_5.py:613,634,838`) and falls through `wrap_view`'s generic handler rather
  than `dispatch_detail`'s

**Two 400 shapes exist that the generator would never guess.** `updateWebUser`
and `inviteWebUser` return `{"errors": [...]}` — plural, a list — because
`WebUserValidationException` normalises its message to a list
(`corehq/apps/api/validation.py:31-33`) and both call sites raise it as an
`ImmediateHttpResponse`, bypassing tastypie's `BadRequest` conversion entirely.
And `sso/v1` answers a missing `username` or `password` with Django's
`HttpResponseBadRequest('Missing required parameter: username')`
(`SingleSignOnResource`, `v0_4.py:754,757`) — a literal string under
`text/html`, not JSON.

**Form submission is not tastypie at all**, so none of the above applies to it:
`post_api`/`post` (`corehq/apps/receiverwrapper/views.py:278-320`) are plain
Django views whose 401 and 403 render through `handler403 = no_permissions` as
HTML.

**Some operations can never return a 429**, so declaring the throttle response
universally would be wrong. `UserDomainsResource.Meta` (`v0_5.py:1348`) is a
plain `object` rather than `CustomResourceMeta`, so it never sets a throttle and
tastypie's default `BaseThrottle.should_be_throttled` always returns `False`.
`getIdentity` is the same.

**And one 401 is really a rate limit.** The blacklist response means "too many
requests" but is served under a 401. A client branching on status code alone
cannot distinguish it from an auth failure, which is worth stating in the
response description rather than leaving to be discovered.

The bare-array 400 the audit's summary mentions is the `{"errors": [...]}` shape
above, now traced.

## Goal

Every operation in every generated spec declares the error responses it can
actually return, with the body shape it actually returns, sourced from the code
paths that produce them.

## Non-goals

- **Fixing the inconsistency.** Four 404 shapes is a defect, but changing error
  bodies is a breaking API change for existing integrators and belongs in its
  own discussion. This work documents what is, accurately. Where the behaviour
  is plainly a bug rather than an inconsistency, it is already filed: SAAS-20192
  through SAAS-20202 cover eleven such cases, including three where an uncaught
  exception returns 500 where a 400 or 404 belongs.
- **Documenting 500s as an expected response.** A 500 is a defect, not a
  contract. The tastypie exception body is recorded here as evidence of what the
  API does, not as something to publish.

## Approach

**Declare shared response components once, reference them per operation.**
`components.responses` gains an entry per distinct shape — not per status code,
since one code has several shapes. Each operation then references the ones its
own code path can produce.

The mapping from operation to responses is derived where the code makes that
possible and declared where it does not:

- **Derivable, with care.** Authentication and authorization responses follow
  from the resource's authentication class, which the generator already reads to
  produce the "Requires the `x` permission" sentence. But the derivation must
  emit _both_ 401 shapes — the empty challenge response and the JSON one — since
  which one a caller sees depends on how the credential failed, and the empty
  one is the common case. `HqBaseResource`'s privilege and blacklist responses
  apply to every resource that inherits it.
- **Derivable, but not universal.** The throttled response applies only where a
  throttle is actually configured. `CustomResourceMeta` sets one, but not every
  documented resource uses it: `UserDomainsResource.Meta` (`v0_5.py:1348`) is a
  plain `object`, so that resource can never return 429. The generator must read
  the resource's `Meta` rather than assume, or it will publish a response the
  endpoint cannot produce. Where a throttle does apply, its `Retry-After` header
  is part of the contract and belongs in the response as a declared header
  rather than in prose.
- **Not derivable at all.** Whether a resource's 403 has a body, and which of
  the four 404 shapes an operation produces, depends on which code path raises —
  and in two cases on Django's HTML error handlers rather than on tastypie.
  These have to be declared per operation, from a trace, not inferred from the
  class.
- **Declared.** Validation failures are resource-specific: which fields can be
  rejected, and with which of the three 400 bodies. These go in `Docs`, beside
  the resource, the same way parameters and field schemas already do.

The generator keeps its existing property: nothing is published that the code
does not support. A declared error response that no code path can produce is as
much a lie as a missing one, and the temptation here is to attach a plausible
set of four or five errors to every operation because it looks thorough.

## Verification

The gates this project already has do not cover error responses, because both
work from success payloads. Two additions:

- **Extend the contract tests.** `tests/test_contract.py` fetches real responses
  and validates them against the spec. It gains cases that provoke real errors —
  an unauthenticated request, a request without the required permission, a
  missing record, a malformed filter — and asserts the response's status _and
  body shape_ match what the spec declares for that operation. This is the only
  check that can catch a plausible-but-wrong error declaration, and it is the
  reason this work is worth doing properly rather than by inspection.
- **Assert no operation declares an undeclarable response.** For the derivable
  categories, a test walks the catalogue and checks that an operation declares
  the authentication and throttle responses its resource's configuration
  implies, and does not declare ones it cannot produce.

Expect the contract tests to surface further discrepancies as they are written.
That is the point: the audit found 42 error-response findings by reading code,
and a test that provokes the error is a stronger instrument than reading.

## Sequencing

1. Establish the full set of distinct shapes, including tracing the bare-array
   400 the audit reports. Record each with the code path that produces it.
2. Declare them as shared components, and wire the derivable categories
   (authentication, authorization, privilege, throttle) through the generator.
3. Extend the contract tests to provoke and verify each derivable category on
   the two resources they already cover.
4. Declare resource-specific validation responses for the documented APIs, one
   resource at a time, each verified against a provoked response.

Steps 1 to 3 are the load-bearing part: they establish the vocabulary and the
gate. Step 4 is repeatable backfill once those exist.

## Risk

The honest risk is scope. Forty-two findings is a lot, several are surprising,
and it is tempting either to document an idealised error contract (fast, wrong)
or to fix the inconsistencies while documenting them (slow, and a breaking
change). Both are out of bounds here. If the work reveals that a resource's
error behaviour cannot be described without first changing it, that resource's
errors stay undocumented and the finding gets filed — an accurate gap is worth
more than an inaccurate description.
