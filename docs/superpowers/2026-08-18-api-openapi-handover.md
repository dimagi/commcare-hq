# CommCare API OpenAPI: handover, rulings and follow-ups

Branch: `nh/api-openapi-specs` (44 commits on top of `master` at `ef148302e5a`)
Date: 2026-08-18

> **2026-08-20 update:** the RST rendering path this document describes was
> removed on 2026-08-20 (see
> `docs/superpowers/specs/2026-08-20-api-rst-reduction-design.md`). The
> reference is now Redoc pages built by `yarn openapi:docs` and served at
> `/api/docs/`. Ruling 15 below and known issue 13 no longer apply — the
> renderer they describe is gone. Ruling 15's own reasoning was an argument
> _against_ using ReDoc, on the grounds that it renders client-side and so is
> invisible to grep and to agents; the project adopted ReDoc anyway, because the
> pages are now pre-built to static HTML at deploy time, which removes the
> objection ruling 15 raised. The rulings and known issue are left as written
> below — they were correct at the time.

Companion documents:

- Design: `docs/superpowers/specs/2026-08-17-commcare-api-openapi-design.md`
- Plan: completed and removed on 2026-08-20; the design and this document remain
  the record.
- Maintainer guide: `corehq/apps/api/openapi/README.md`

`docs/superpowers/` is excluded from the Sphinx build, so this file is internal
and does not publish to readthedocs.

## Status

The branch generates OpenAPI 3.0.3 specifications for the CommCare data APIs
from the API code, and makes those specs the source of truth for the published
documentation pages. Seven APIs are documented end to end (mobile workers,
cases, forms, groups, locations v1 and v2, location types, lookup tables, and
Case API v2); the rest are generated structurally but carry no field
descriptions.

Verified on the final tree:

| Gate                                                                                           | Result                      |
| ---------------------------------------------------------------------------------------------- | --------------------------- |
| `uv run pytest --reusedb=1 corehq/apps/api corehq/apps/hqcase`                                 | 863 passed, 0 failed        |
| `uv run ./manage.py generate_openapi --check`                                                  | up to date                  |
| `openapi_spec_validator` over all 21 specs                                                     | valid                       |
| `npx @stoplight/spectral-cli lint --ruleset docs/api/spec/.spectral.yaml docs/api/spec/*.json` | 0 errors, 14 warnings       |
| `cd docs && uv run make html`                                                                  | build succeeded, 0 warnings |

The 14 Spectral warnings are all `operation-description`, on the specs that are
deliberately undocumented. That is the expected baseline; it should fall as
those APIs get documented, and any other rule appearing is a regression.

## Rulings made during implementation

Decisions taken without asking, in the order they were made, each with what it
costs if the decision was wrong.

1. **Worked in the existing checkout rather than a new git worktree.** The
   working virtualenv and the running dev server are bound to this path. _Cost:
   no filesystem isolation from concurrent work in this checkout._
2. **Used `settings.BASE_DIR` for the repo root**, not the plan's
   `settings.filepath`, which does not exist. _Cost: none._
3. **Read jsonobject properties from `cls._properties_by_key`**, not the plan's
   `_properties_by_name`, which does not exist. _Cost: none;
   `_properties_by_attr` is the only alternative and is identical here._
4. **Called jsonobject's callable-wrapped defaults** instead of skipping
   callables. Every jsonobject default is a lambda, so the plan's guard would
   have dropped all of them. _Cost: a default that cannot be computed at import
   time is omitted, which is what the original guard did anyway._
5. **Amended the plan commit** with corrections 2–4 rather than adding a third
   documentation commit. _Cost: the reviewed plan text differs by exactly those
   three corrections._
6. **Left Task 2's commit mixing `ruff format` output with logic** rather than
   rewriting history mid-branch. _Cost: a noisier `urls.py` diff; see follow-up
   F1._
7. **Narrowed `ruff format` scope for every later task** to files that task
   created or edited, instead of whole app trees as the plan said. _Cost: some
   pre-existing files stay unformatted, which is the status quo._
8. **Batched Tasks 3–5 into a single dispatch** (three small pure-function
   modules of the same shape). _Cost: one review surface covering three
   modules._
9. **Added a catalogue uniqueness test** for `(resource_name, version)`, since
   duplicate `operationId`s are invalid OpenAPI and `openapi-spec-validator`
   does not reject them. _Cost: one extra test._
10. **Moved the management command** to `corehq/apps/api/management/commands/`.
    Django only discovers commands in an installed app, and the plan put it in a
    subpackage where `./manage.py generate_openapi` would not exist. _Cost:
    none; the planned location was simply broken._
11. **Diagnosed the "46 pre-existing errors" as a stale test database**, not an
    environment limitation, after two subagents had written them off. _Cost:
    none — `--reusedb=migrate` makes them pass._
12. **Folded a minor finding into Task 9's fix round** rather than deferring it,
    because that file is the template eight later APIs copy. _Cost: one extra
    edit in a file already being changed._
13. **Rejected a reviewer finding**: `eulas` publishing `type: string` is
    correct, because Tastypie's `CharField.convert()` calls `str()` on the
    value, so the wire value genuinely is a string. _Cost: if wrong, the spec
    understates a list-shaped field._
14. **Corrected the source RST rather than reproducing its error.**
    `docs/api/list-webusers.rst` describes web usernames as "including domain",
    which is false. This became a general rule for later tasks. _Cost: published
    wording diverges from the old pages, which is the intent._
15. **Switched to `sphinxcontrib-openapi`'s `httpdomain` renderer rather than
    falling back to ReDoc.** The default renderer emits no response field
    documentation at all; ReDoc would show it but renders client-side, making it
    invisible to grep and to agents reading the published HTML. _Cost: the newer
    renderer is less widely used._
16. **Exactly one page renders each spec**, since the renderer cannot filter by
    path; a second page covering the same resource becomes a short summary with
    a cross-reference. _Cost: some pages are thinner than before._
17. **Excluded `docs/superpowers/` from the Sphinx build.** _Cost: the design,
    plan and this document are not browsable on readthedocs, which is intended._
18. **Resumed a stalled agent to verify and commit** rather than re-running Task
    11 from scratch. _Cost: none; it recovered._
19. **Closed a 15-hour test-database investigation** and recorded the
    case/form/group resource-test verification as _not performed, blocked by
    test-database state_ rather than as environmental-and-therefore-fine. _Cost:
    one near-zero-risk behaviour check went unverified._
20. **Fixed both spec-versus-runtime divergences immediately** (three location
    fields missing from the schema; two user fields present in the schema but
    never returned) rather than deferring them. _Cost: one extra branch in
    `operations.py` and two extra tests._
21. **Hardened the implicit `type` discriminator with a test** rather than
    redesigning the mechanism. _Cost: the rule is documented by a test rather
    than by an explicit marker key._
22. **Used `anyOf`, not `oneOf`, for the ext-PUT request body.** My earlier
    `oneOf` instruction was wrong: the branches differ only by their required
    sets, so a valid creation payload matched both and was rejected. _Cost:
    `anyOf` under-constrains rather than over-constrains._
23. **Added the example-validation gate** that reviews identified as the missing
    check, after a schema and its example were found to be self-consistently
    wrong twice. _Cost: none._
24. **Cut Spectral from 288 warnings to 14** by emitting global tags, emitting
    `PaginationMeta` only when referenced, and disabling
    `path-keys-no-trailing-slash` as inapplicable — CommCare's URLs are
    trailing-slash by routing design. _Cost: if CommCare ever drops trailing
    slashes, that rule will not flag it, though that would be a deliberate API
    change._
25. **Corrected the final fix wave's own new breakage** despite the process
    allowing only one wave, because it published response bodies that never
    arrive — the exact defect class this project exists to prevent. _Cost: one
    extra review cycle._

## What you should know before opening a PR

- **The whole-branch review initially returned "not ready", and was right.** The
  plan never implemented the _declaring_ half of query-parameter documentation,
  so for a while the specs published **less** than the RST pages they replaced.
  Fixed: `case-v1` now publishes 20 query parameters, `form-v1` 14, `user-v1` 6.
- **Two commits fix pre-existing test bugs unrelated to this work**
  (`9ecc2594b8e` and `6e99159229d`), both order-dependent assertions that passed
  alone and failed in a full run. They are separate commits and could be split
  out into their own PR.
- **`sso-v1` POST declares `200` with no response body shape.** It really
  returns a user object; the shape was omitted rather than guessed.
- **Nine specs are structurally valid but carry no field descriptions.** That is
  the plan's deliberate first-slice boundary, recorded in the README. The final
  reviewer's point is worth acting on: in `bundle.json` an agent cannot
  distinguish documented from undocumented surface (follow-up D1).
- **Commit hygiene needs a grooming pass** before review (follow-up F1).

## Follow-up items

### A. Published-spec accuracy

1. **`case-v1` documents the wrong parameter spellings.** It publishes `name`
   and `type`, which work only through the generic unconsumed-parameter fallback
   (a non-analyzed term match). The explicitly supported parameters are
   `case_name` and `case_type` — `corehq/apps/api/es.py:357-358` declares
   `TermParam('case_name', 'name', analyzed=True)` and
   `TermParam('case_type', 'type', analyzed=True)`, so the supported spellings
   use analyzed matching with different semantics. Document `case_name` and
   `case_type`; drop the others or describe how they differ.
2. **`form-v1`'s `appVersion` is documented as unsupported.** The generic
   fallback terms a top-level `appVersion` field, but
   `corehq/apps/es/mappings/xform_mapping.py` maps it only under `form.meta`, so
   it always returns zero results. The real fix is upstream: either support the
   parameter properly or remove it from the API. The old RST page claimed it
   worked, so this predates the branch.
3. **`sso-v1` POST has no declared response body.**
   `SingleSignOnResource.post_list` returns a user object at 200; declare the
   shape.
4. **Detail-GET has no query-parameter mechanism.** The `<field>__full=true`
   toggles are documented on list paths only, though they work on detail paths
   too.
5. **`required` is not emitted on Tastypie request bodies.** Deriving it from
   `blank` was tried and reverted: `blank` defaults to `False` and every
   documented write resource bypasses Tastypie hydration, so the derivation
   produced wrong answers such as `email` being required. Per-resource
   declaration is the only correct route.

### B. Gates and coverage

6. **Live-response contract validation covers only `user-v1` and `group-v1`**
   (`corehq/apps/api/openapi/tests/test_contract.py`). Extend it to `case-v1`
   and `form-v1`; the function-view endpoints (`case_api`, bulk fetch) are not
   reachable through `APIResourceTest` and need a different harness.
7. **The example reverse-check is top-level only.** It compares top-level
   property names and does not recurse into nested objects or array items.
8. **`OAS30Validator` without request/response context exempts both `readOnly`
   and `writeOnly` from `required` checks**, so a response example missing a
   required `readOnly` field passes silently.
9. **The bulk-array gate depends on examples staying branch-representative.**
   Nothing enforces that a bulk example contains one item per `create` branch; a
   uniform single-shape example would not exercise the branching.
10. **`generate_openapi --check` does not detect orphan spec files.** Removing a
    `doc_slug` leaves its committed spec behind and nothing complains.
11. **`DOCUMENTED_SLUGS` duplicates the catalogue.** It could be derived from
    `ApiEntry` (for example a `documented=True` flag) instead of being a second
    list to keep in sync.

### C. Tooling and dependencies

12. **`jsonschema.RefResolver` is deprecated** (installed jsonschema 4.26.0).
    `OAS30Validator` accepts a `referencing.Registry` via `registry=`. The
    deprecation warning is currently invisible because `pyproject.toml` sets
    `-pno:warnings`, so this will surface as a hard failure after upstream
    removal.
13. **`sphinxcontrib-openapi` renders only the first branch of an
    `anyOf`/`oneOf` field list.** The rendered example still shows all shapes,
    so a reader can infer the variance, but the field list is incomplete for
    Case API v2's bulk and ext-PUT bodies.

### D. Scope and product decisions

14. **Consider excluding undocumented slugs from `bundle.json`**, or tagging
    them `x-undocumented`. An agent consuming the bundle currently cannot tell
    documented surface from structurally-generated stubs.
15. **Consider generating `bundle.json` at docs-build time** rather than
    committing it. It is pure duplication of the per-API specs and already
    around 10,000 lines of the committed diff.
16. **Document the nine remaining thin specs**: `application-v1`,
    `bulk-user-v1`, `det-export-v1`, `fixture-v1`, `report-config-v1`,
    `report-data-v1`, `sso-v1`, `user-domains-v1`, and `web-user-v1`'s own
    (non-inherited) fields. The README's procedure covers how.
17. **Document the remaining non-Tastypie APIs**, which this slice left out:
    messaging-event, the OData case and form feeds, UCR data, generic inbound,
    case and form attachments, OpenRosa form submission, and OTA restore. Case
    API v2 proved the `@api_docs` route works for hand-written views.
18. **A live `/api/openapi.json` endpoint** was deferred by design, not ruled
    out. It would give integrators a stable always-current URL; it needs a
    public view, a cache strategy, and a decision about whether the spec varies
    by plan or feature flag.
19. **Admin and accounting resources stay outside the catalogue** by design.
    They register through a different mechanism and are not publicly documented.

### E. Pre-existing bugs found along the way

None of these are caused by this branch; all were found while working on it.

20. **Tastypie's own `.../schema/` endpoints return HTTP 500 for 28 of 33
    resources.** `get_schema()` calls `get_object_list()`, which plain
    `Resource` subclasses do not implement. Only the `ModelResource` ones and
    `UserDomainsResource` work. Decide whether to fix these or remove the route
    — the generator does not use them.
21. **`is_new_case` in `corehq/apps/hqcase/api/updates.py` is a plain `= True`
    class attribute that jsonobject turns into a real settable property.** A
    client that sends `is_new_case` in a payload could flip the create/update
    code path in `get_caseblock()`. It is excluded from the published schema,
    but the underlying behaviour is untouched.
22. **`form-v1`'s `archived` is declared `CharField` while `dehydrate_archived`
    returns a boolean.** The spec was corrected via `field_schemas`, but the
    resource declaration is still misleading to read.
23. **`eulas` is declared `CharField` over a list-valued model attribute.** The
    wire value is a string because `convert()` calls `str()` on the list, which
    is odd rather than wrong.
24. **Two order-dependent test bugs were fixed here**
    (`corehq/apps/api/tests/case_resources.py`,
    `corehq/apps/api/tests/test_user_resources.py`). Both compared unordered
    database results against ordered literals and passed in isolation. The same
    pattern may exist elsewhere in the suite.

### F. Branch hygiene

25. **Groom the branch before review.** Two commits mix `ruff format` output
    with logic changes (`fc3aae7aa1c` reformats `urls.py`; `e363405d21b` lands
    `schema.py` fixes with the builder), and there are three fix-on-fix pairs
    that could be squashed (`b1bb2c9f99e`/`4187e9f23f2`,
    `df74ba7c112`/`7c065e2557d`, `1da0b683204`/`98ec92f160a`). The repo's
    `branch-grooming` skill covers this, including its convention of deleting
    the design and plan documents in a closing commit.

## The most useful lesson from the run

Five defects reached committed artifacts, and every one was the same shape: a
spec that was internally consistent and wrong about the API. A schema agreed
with its own example because both were derived from the same bad assumption; a
declared type disagreed with what a `dehydrate_` method really returns; a
response schema listed fields the API never sends.

Checks that compare our own outputs to each other cannot catch that class. Only
comparing against real behaviour can — which is what `tests/test_contract.py`
does, and why extending its coverage (follow-up B6) is the highest-value work
remaining.
