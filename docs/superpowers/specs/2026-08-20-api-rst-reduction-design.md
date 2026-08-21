# Reducing the reStructuredText API documentation

Date: 2026-08-20 Depends on: `2026-08-20-api-docs-pages-design.md` and
`2026-08-20-api-error-responses-design.md` (this lands after both)

## Purpose

Once each API has a Redoc reference page, the reStructuredText pages under
`docs/api/` stop being the reference and become the wrong place to keep one.
This work reduces them to what reStructuredText is actually good for — advice on
using the CommCare APIs as a whole — and points readers at the reference pages
for per-endpoint detail.

## The precedent that shapes this design

This has already gone wrong once, in the small. When
`docs/api/mobile-worker.rst` was reduced to a pointer, it silently dropped
constraints that only that page carried: with account confirmation, `password`
must be omitted and `email` must be present (enforced by
`validate_new_user_input()`), and the first phone number becomes the default. A
reviewer caught it and the prose was moved into the spec's operation
description.

That was one page. Applying the same reduction to twenty-six without a
deliberate sweep would repeat the loss at scale, and the losses would be
invisible — nobody notices a constraint that is no longer documented until an
integrator hits a 400 they cannot explain.

So the governing rule of this design: **nothing is deleted until its content has
a home.**

## Current state

> **Correction, 2026-08-20.** Three claims below are out of date:
>
> - `lookup-table-item-v1` and `lookup-table-item-v2` are **not** undocumented.
>   Both specs are complete and fully described, and `fixture.rst` rendered all
>   three lookup-table specs — the gap this section describes was closed before
>   this design was written. (Since the reStructuredText rendering path was
>   removed, no page renders a spec at all; each of the three gets its own link
>   to its reference page instead.)
> - Ten specs are fully described, not none: `case-v1`, `form-v1`, `group-v1`,
>   `location-type-v1`, `location-v1`, `location-v2`, `lookup-table-item-v1`,
>   `lookup-table-item-v2`, `lookup-table-v1`, `user-v1`.
> - `cases-v2.rst` already renders `case-v2`, whose fields are almost entirely
>   undescribed. The downgrade this design warns against has therefore already
>   shipped on that page, and is corrected by the description backfill rather
>   than by holding the reduction back.

Twenty-seven pages, in three groups:

**Already rendering a spec (9):** `cases-v1`, `cases-v2`, `fixture`,
`list-forms`, `list-mobile-workers`, `locations-v1`, `locations-v2`,
`location-types`, `user-group`.

**Reduced to pointers (3):** `list-groups`, `mobile-worker`, `form-data`.

**Still hand-written (15):** `application-structure`, `bulk-upload-cases`,
`bulk-user`, `det-exports`, `download-report-data`, `form-submission`,
`import-app`, `index`, `list-reports`, `list-webusers`, `messaging-events`,
`ota-api-restore`, `sso`, `user-domain-list`, `webuser`.

There is also a gap in the other direction. The nine converted pages render nine
specs, but `lookup-table-item-v1` and `lookup-table-item-v2` are fully described
and rendered by **no page at all** — `fixture.rst` renders `lookup-table-v1`
only. Two complete specs are therefore invisible in the published documentation
today. The per-API reference index removes that failure mode by listing every
documented spec rather than every page someone remembered to write, which is an
argument for doing the reference pages first.

The hand-written group splits further, and this is the part that determines
sequencing:

- **Pages whose API has a spec that is fully described** — none remaining; the
  nine already converted covered those.
- **Pages whose API has a spec that is generated but thin** (no field
  descriptions): `application-structure`, `bulk-user`, `det-exports`,
  `download-report-data`, `list-reports`, `list-webusers`, `sso`,
  `user-domain-list`, `webuser`. Reducing these would trade a real description
  for an empty one.
- **Pages whose API has no spec at all**: `bulk-upload-cases`,
  `form-submission`, `import-app`, `messaging-events`, `ota-api-restore`.
  Nothing to point at.

## Goal

`docs/api/` ends up as:

- **A short guide** covering what applies across the APIs: authentication and
  how to get an API key, the domain-scoped URL structure, versioning and what a
  version bump means, pagination, rate limits and what to do when throttled, the
  required software plan, and where the reference lives.
- **One entry per API**, each a title, a sentence of orientation, and a link to
  its reference page.
- **Verbatim pages for the APIs the generator does not yet cover**, untouched
  until it does.

## Non-goals

- Deleting the pages for APIs without specs. They are the only documentation
  those APIs have.
- Reducing a page whose spec has no field descriptions. That is a downgrade
  dressed as a cleanup.
- Rewriting the guide content from scratch. Most of it already exists, scattered
  across the pages being reduced; the work is consolidation, not authorship.

## Approach

**A sweep before any deletion.** For each page in scope, enumerate what it
contains and classify every item:

1. **Already in the spec** — delete from the page.
2. **Belongs in the spec** — move it into the relevant `Docs.description` or
   field description, regenerate, and confirm it appears on the reference page
   _before_ deleting the prose. Preconditions, cross-field rules and "this field
   is only returned when…" notes fall here.
3. **Belongs in the guide** — authentication instructions, plan requirements,
   URL conventions, anything that is about the APIs collectively.
4. **Genuinely obsolete** — describes behaviour the code no longer has. Delete,
   and note it, because an obsolete instruction that has been published is worth
   knowing about.

The sweep's output is a checklist per page, committed alongside the change, so a
reviewer can see what happened to each item rather than trusting that nothing
was lost.

**Order of work.** Reduce a page only when its spec is fully described. That
makes this work depend on description backfill for nine APIs, and on the
error-response design for the parts of those pages that document failure
behaviour — several of the hand-written pages document error conditions the
specs will not describe until that work lands.

The practical consequence: this is not one change. It is the guide, then one
page reduced per API as that API's spec becomes complete. The guide can be
written first and is useful immediately.

## Structure of the guide

One page, replacing the overview content currently spread across
`docs/api/index.rst` and repeated in the preamble of most per-API pages:

- What the CommCare APIs are, and the plan requirement
- Authentication: API key, Basic, Digest, OAuth2, with the header format —
  currently a link to a Confluence page from every single API page, which is
  worse than stating it once
- URL structure: `/a/<domain>/api/<resource>/<version>/`, and the user-scoped
  variants
- Versioning: what a version bump signals, and that additive changes do not bump
- Pagination: `limit` and `offset`, the `meta` envelope, and cursor pagination
  where it applies
- Rate limiting: that throttling exists, and the `Retry-After` header
- Where the reference is, and how to read it

Each API then gets its entry in the toctree pointing at its reference page.

## Verification

- The docs build stays at zero warnings, and every `:doc:` and external link in
  the reduced pages resolves.
- A test asserts that every entry in `docs/api/index.rst`'s toctree exists, so a
  reduction cannot orphan a page or leave a dangling reference.
- For each reduced page, the sweep checklist is part of the commit, and the
  claim "this item is now in the spec" is checkable by looking at the rendered
  reference page.
- The pages for uncovered APIs are byte-identical before and after — asserted by
  the diff, not by inspection.

## Risk

The failure mode is the one already demonstrated: a constraint that lived only
in prose disappears, and nobody notices until an integrator is confused. The
sweep is the mitigation, and it only works if it is done per item rather than
per page — reading a page and concluding "this all looks like reference
material" is how the mobile worker constraints were lost the first time.

A second, smaller risk: the guide becomes a dumping ground. Anything that is
about one API belongs in that API's spec, not the guide. If the guide grows past
a page or two, that is a signal something was routed there to avoid deciding
where it really goes.
