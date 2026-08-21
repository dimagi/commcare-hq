# Sweep: lookup-table-v1, lookup-table-item-v1, lookup-table-item-v2

Source page: `docs/api/fixture.rst` (463 lines at d1020d7d5fc)

One combined checklist, per the task brief ("one combined file is fine
here since it is one page covering three specs"): all three specs are
served from the same page and the same two resource modules.

Reference URLs: `/api/docs/lookup-table-v1/` (6/6), `/api/docs/lookup-table-item-v1/`
(6/6), `/api/docs/lookup-table-item-v2/` (6/6).

Resource code:
- `LookupTableResource` in `corehq/apps/fixtures/resources/v0_1.py` —
  lookup-table-v1.
- `LookupTableItemResource` in `corehq/apps/fixtures/resources/v0_1.py` —
  lookup-table-item-v1.
- `LookupTableItemResource` in `corehq/apps/fixtures/resources/v0_6.py`,
  which subclasses v0_1's and does **not** redeclare `field_schemas` (or
  the tastypie fields at all) — lookup-table-item-v2. `docs.py`'s
  `collect_docs()` walks the resource's full MRO and shallow-merges every
  `Docs.field_schemas` dict found, so a `field_schemas`/field-`help_text`
  edit on the v0_1 class reaches v2 automatically. `Docs.description` is
  a plain string, not a dict, so it is **not** merged — v0_6 fully
  overrides it, and a description-level fact meant for both v1 and v2
  had to be added to both classes' `Docs.description` by hand (verified
  by regenerating and reading both specs, per the brief's instruction not
  to assume).

Same-module trap: `v0_1.py` also defines `FixtureResource` (→
`fixture-v1`, catalogued separately at `catalogue.py:53`) and
`InternalFixtureResource`. Neither was touched — confirmed by diffing
`docs/api/spec/fixture-v1.json` after `generate_openapi`, which is
byte-identical to its pre-sweep contents.

## `docs/api/fixture.rst`, "Fixture Data APIs (or Lookup Tables)" section (old lines 1-97)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose ("Retrieve all data associated with a fixture") | out of scope | describes `/api/fixture/v1/`, served by `FixtureResource` → `fixture-v1`. `fixture-v1` has no `Docs` and is rendered by no page (per the task brief); deliberately out of scope for this consolidation. Removed, not migrated anywhere |
| Base URLs (by item id / by `fixture_type` / list all) | out of scope | same — `fixture-v1` |
| Authentication note | out of scope | same, and would have duplicated `docs/api/index.rst` Authentication section anyway |
| Permission Required: Edit Apps | out of scope | same |
| Input parameter `fixture_type` | out of scope | same |
| Output values `id` / `fixture_type` / `fields` | out of scope | same |
| Note: `fixture_type` = table name = Table ID column in the fixtures UI | out of scope | same |
| Sample Input / Sample Output | out of scope | same |

## `docs/api/fixture.rst`, "Bulk Upload Lookup Tables" section (old lines 99-176)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose (create/edit lookup tables via Excel upload) | out of scope | `POST /a/{domain}/fixtures/fixapi/` is `upload_fixture_api`, a plain Django view (`corehq/apps/fixtures/urls.py`), not a Tastypie `Resource` — it has no `ApiEntry` in `catalogue.py` and is not part of the OpenAPI generation pipeline at all, so there is no spec slug for it on this page or anywhere else in the project |
| URL, Method, Authorization | out of scope | same |
| Input params `file-to-upload` / `replace` / `async` | out of scope | same |
| Sample cURL request | out of scope | same |
| Response params `code` / `message` / `status_url` | out of scope | same |

## `docs/api/fixture.rst`, "Lookup Table Individual API" section (old lines 178-308) — lookup-table-v1

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose "Manage lookup tables via API calls" | in spec | `lookup-table-v1.json`, operation `description` (`LookupTableResource.Docs.description`) |
| Supported Methods table (GET/POST/PUT/DELETE) | in spec | reflected by which operations exist per path in `lookup-table-v1.json` |
| Authentication note | in guide already | `docs/api/index.rst`, Authentication section |
| List: Base URL, HTTP Method | in spec | path + `get` operation |
| List Sample Output `meta` block | in guide already | `docs/api/index.rst`, Pagination section |
| List Sample Output `fields` / `id` / `is_global` / `resource_uri` / `tag` | in spec | `properties.*.description` on `LookupTableResource` |
| Create: URL, POST method | in spec | path + `post` operation |
| Input param `tag*` (marked required) | considered and rejected | genuinely used to reject duplicate creates, but the generator's `request_schema()` (see `operations.py:232-244`) deliberately derives no `required` list for hand-rolled `obj_create`/`obj_update` resources — same documented limitation as the location-v2 sweep. No `required`-shaped hook exists to restate this without duplicating the field description |
| Input param `fields*` (marked required) | belongs in spec (corrected) | **inaccurate as written** — `LookupTableResource.obj_create()` does `data.get('fields', [])`, so a create request that omits `fields` succeeds with an empty field list; it is not required. Added "Optional on create, defaulting to an empty list." to `fields` help_text, regenerated, confirmed in spec |
| Input param `is_global` "default: false" | belongs in spec | confirmed: `data.get('is_global')` absent from `data` dict when omitted, so the model's `is_global = models.BooleanField(default=False)` applies. Added "Optional on create; defaults to false if omitted." to `is_global` help_text, regenerated, confirmed |
| Sample Input (create) | in spec (implicit) | illustrates fields already covered above |
| Edit or Delete: URL, PUT/DELETE methods | in spec | path + operations |
| Sample Input (edit) omits `is_global` | belongs in spec | this is the live "replace vs merge" question the brief calls out for lookup tables. Confirmed in `obj_update()`: `is_global`, `fields`, `item_attributes` are each independently gated by `'x' in bundle.data` — an omitted key keeps its current value. `tag` is different: it is required on every PUT (`if 'tag' not in bundle.data: raise BadRequest`) and must equal the existing value (`if bundle.obj.tag != bundle.data['tag']: raise BadRequest("...cannot be changed")`). Added this whole picture to `LookupTableResource.Docs.description`, regenerated, confirmed |
| (implicit) create rejects a duplicate tag on the domain | belongs in spec | confirmed: `if LookupTable.objects.domain_tag_exists(kwargs['domain'], tag): raise BadRequest(...)`. Added to `tag` help_text, regenerated, confirmed |
| (implicit) `tag` is immutable after creation | belongs in spec | same `obj_update()` check as above. Added to `tag` help_text alongside the duplicate-create rule, regenerated, confirmed |
| (implicit) on PUT, `fields` if provided replaces the whole list | belongs in spec | confirmed: `bundle.obj.fields = [TypeField(**adapt(f)) for f in bundle.data['fields']]` is a wholesale reassignment, not a per-item merge. Added to `fields` help_text, regenerated, confirmed |

## `docs/api/fixture.rst`, "Lookup Table Rows API" section (old lines 311-463) — lookup-table-item-v1 (and v2, uncovered by the old page)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose "Manage lookup table rows via API calls" | in spec | `lookup-table-item-v1.json` / `-v2.json`, operation `description` (`Docs.description` on each resource) |
| Supported Methods table | in spec | reflected by which operations exist per path |
| List: Base URL, HTTP Method | in spec | path + `get` operation, both specs |
| List Sample Output `meta` block | in guide already | `docs/api/index.rst`, Pagination section |
| List Sample Output `data_type_id` / `fields` / `id` / `sort_key` | in spec | `properties.*.description` on `LookupTableItemResource` (v0_1), inherited by v2 |
| Create: URL, POST method | in spec | path + `post` operation |
| Input param `data_type_id*` (marked required) | belongs in spec | confirmed: both `obj_create()` and `obj_update()` raise `BadRequest("data_type_id must be specified")` when absent. Added "Required when creating or updating a row; a request without it is rejected." to `data_type_id` help_text, regenerated, confirmed in both v1 and v2 |
| Input param `fields*` (marked required) | belongs in spec (corrected) | **inaccurate as written**, same shape as the table-level `fields*` claim above. Traced through tastypie: `FieldsDictField.hydrate()` falls back to `ApiField.hydrate()` when `'fields'` is absent from the request, which returns `getattr(bundle.obj, 'fields', None)` — on a freshly-constructed `LookupTableRow`, `fields = AttrsDict(..., default=dict)` gives `{}`, not `None`, so no `ApiFieldError` is raised and the row is created with no fields. Added "Optional on create, defaulting to no fields." to `fields` help_text, regenerated, confirmed in both v1 and v2 |
| Sample Input (create) | in spec (implicit) | illustrates fields already covered above |
| Edit or Delete: URL, PUT/DELETE methods | in spec | path + operations, both specs |
| Sample Input (edit) changes one field's value | belongs in spec | confirmed in `obj_update()` → `full_hydrate()` → `FieldsDictField.hydrate()`: when `'fields'` **is** present, the hydrated value is built purely from the submitted dict, so any field name present on the existing row but omitted from the request is dropped, not preserved. Added "On update, if provided, this replaces the entire fields dict -- field names omitted from the submitted value are removed from the row." to `fields` help_text, regenerated, confirmed in both v1 and v2 |
| (implicit) `sort_key` is server-assigned on create | belongs in spec | confirmed in `obj_create()`: after `full_hydrate()` runs (which would accept a client-submitted `sort_key`), the line `bundle.obj.sort_key = LookupTableRow.objects.filter(...).aggregate(value=Max('sort_key') + 1)["value"] or 0` unconditionally overwrites it. Added "On create, always assigned by the server as one greater than the current maximum for the table; any value submitted by the client is ignored." to `sort_key` help_text, regenerated, confirmed in both v1 and v2 |
| (implicit) PUT with neither `fields` nor `item_attributes` is a no-op | belongs in spec | confirmed in `obj_update()`: `if 'fields' in bundle.data or 'item_attributes' in bundle.data: bundle.obj.save()` — a request that only sends `data_type_id` still passes validation and returns success, but nothing is persisted. Because `Docs.description` is a plain string (not merged across the v0_1/v0_6 MRO — see the trap note above), the sentence was added to **both** `LookupTableItemResource.Docs.description` in v0_1.py and v0_6.py, regenerated, confirmed present in both specs |
| lookup-table-item-v2 (entire spec) | new orientation link | the old page never mentioned v2 at all. Added as the third link on the reduced page, with its own sentence distinguishing it (returns the row in the response body on write) from v1 |

## New cross-cutting facts added to the guide

None. `docs/api/index.rst` already carries Authentication, Pagination and
Response format sections that cover the `meta` block and auth header
claims made on this page.

## Resource code changed

Both files in `corehq/apps/fixtures/resources/`:
- `v0_1.py` — `LookupTableResource` (`tag`, `fields`, `is_global`
  help_text; `Docs.description`) and `LookupTableItemResource`
  (`data_type_id`, `fields`, `sort_key` help_text; `Docs.description`).
- `v0_6.py` — `LookupTableItemResource.Docs.description` (the PUT
  no-op sentence only; every other v2 fact is inherited through the
  shared field objects and the merged `field_schemas`, per the MRO note
  above).

## Items considered for promotion and rejected

- **`tag*`/`fields*` (table) and `data_type_id*` (item) "required"
  markings**: `data_type_id` genuinely is enforced with a clean
  `BadRequest` in code, and was promoted (see above). `tag` is enforced
  only on update, not on create (a missing `tag` on create is not
  explicitly checked before `LookupTable(...).save()`, which would raise
  an unhandled `IntegrityError` — a 500, not a clean 400). This is an
  existing code rough edge, not a documentation gap to paper over by
  claiming a validation that does not exist; left unfixed and unclaimed.
  In any case the generator's `request_schema()` does not derive
  `required` for hand-rolled `obj_create`/`obj_update` resources at all
  (same limitation noted in the user-v1, group-v1 and location sweeps),
  so there is no clean way to mark any of these fields formally required
  without a generator change, which is out of scope here.
- **`LookupTableItemResource.obj_create()`'s lookup-table existence
  check does not filter by domain**: `if not LookupTable.objects.filter(id=data_type_id).exists(): raise NotFound(...)`
  checks only that a table with that id exists anywhere, not that it
  belongs to the requesting domain (contrast `obj_update()`, which does
  check `bundle.obj.domain != kwargs['domain']`). This looks like a
  genuine access-control gap, not a documentation question — documenting
  it as intended behavior would be worse than staying silent, and fixing
  it is out of scope for a docs sweep. Flagged for follow-up in the task
  report instead of touched here.
- **`item_attributes` "required" on row create**: the old page's Input
  Parameters table for row creation never listed `item_attributes` at
  all (only `data_type_id*` and `fields*`), so there was no inaccurate
  claim to correct, and adding new documentation of behavior the old
  page never described would be writing new content beyond the sweep's
  scope.
- **Bulk Upload Lookup Tables' `replace`/`async` semantics**: real,
  working behavior of `upload_fixture_api`, but that view has no
  Tastypie resource and thus no OpenAPI spec slug anywhere in the
  catalogue — there is nowhere in this project's OpenAPI docs to promote
  it to. Out of scope, not obsolete; the feature still exists, just
  outside this consolidation.
