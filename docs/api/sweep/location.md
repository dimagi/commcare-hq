# Sweep: location-v1, location-v2, location-type-v1

Source pages:
- `docs/api/locations-v1.rst` (89 lines at deffb65d0c5)
- `docs/api/locations-v2.rst` (257 lines at deffb65d0c5)
- `docs/api/location-types.rst` (73 lines at deffb65d0c5)

One combined checklist rather than three, per the task brief: the three
pages share heavily overlapping prose (serialization notes, pagination
meta blocks, the same location/location-type fields under different
serializations), and location-v1/location-v2/location-type-v1 are all
served by resources in the same module family
(`corehq/apps/locations/resources/v0_5.py`, `v0_6.py`), so classifying a
shared item once and applying it across all three avoided reasoning about
the same sentence three times.

Reference URLs: `/api/docs/location-v1/` (14/14), `/api/docs/location-v2/`
(11/11), `/api/docs/location-type-v1/` (9/9).

Resource code: `LocationResource`/`LocationTypeResource` in
`corehq/apps/locations/resources/v0_5.py` (location-v1, location-type-v1);
`LocationResource` in `corehq/apps/locations/resources/v0_6.py`, which
subclasses v0_5's and redeclares `field_schemas` (location-v2).

## locations-v1.rst

| Item | Bucket | Where it went |
| --- | --- | --- |
| Note pointing to locations-v2 for newer functionality | rewritten | orientation sentence on the reduced page, as prose instead of a `:doc:` cross-reference (the two pages serve different specs, but the brief's rule against leaving one page hopping to another via `:doc:` applies equally here) |
| "Individual locations are presented with the same serialization format in each endpoint" | rewritten | structural framing, not a claim; dropped |
| Sample JSON: `created_at` / `domain` / `external_id` / `id` / `last_modified` / `latitude` / `location_data` / `location_id` / `location_type` / `longitude` / `name` / `parent` / `site_code` | in spec | `location-v1.json`, `properties.*.description` on `LocationResource` |
| Sample JSON: `resource_uri` | in spec | `properties.resource_uri.description`, `Docs.field_schemas['resource_uri']` in v0_5.py |
| Base URL (list) | in spec | path in `location-v1.json` |
| Input params `site_code` / `external_id` / `created_at` / `last_modified` / `latitude` / `longitude` | in spec | `location-v1.json` GET parameters, same names |
| Sample JSON `meta` block | in guide already | `docs/api/index.rst`, Pagination section |
| Base URL (detail) | in spec | path in `location-v1.json`, `{location_id}` operation |
| "This will output the same information ... for a single location" | in spec (implicit) | detail operation's response schema is the same object schema as list |

## locations-v2.rst

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose paragraph (updates serialization, adds create/update, single + bulk) | rewritten | new orientation sentence |
| "Individual locations are presented with the same serialization format in each endpoint" | rewritten | structural framing, dropped |
| Sample JSON: `domain` / `last_modified` / `latitude` / `location_id` / `longitude` / `name` / `site_code` | in spec | `location-v2.json`, `properties.*.description` |
| Sample JSON: `location_data` | in spec (thin, as flagged in the brief) — see promoted note below | base description ("Custom data ... keyed by field name.") already present |
| Sample JSON: `location_type_code` / `location_type_name` / `parent_location_id` | in spec | `Docs.field_schemas` additions in v0_6.py (not declared Tastypie fields; set in `dehydrate()`) |
| Base URL (list) | in spec | path in `location-v2.json` |
| Input param `format` | in spec / in guide already | `location-v2.json` GET parameter; `docs/api/index.rst` Response format section |
| Input params `site_code` / `name` / `location_type_code` / `parent_location_id` | in spec | GET parameters, same names |
| Input params `last_modified.gte` / `.gt` / `.lt` / `.lte` | in spec | GET parameters, same names; confirmed against `LocationResource.build_filters()` (v0_6.py), which maps `k.split('.')` to the ORM lookup |
| `order_by=last_modified` / `-last_modified`, combined with `last_modified.gte` for incremental pulls | in spec | `order_by` parameter enum, generated from `Meta.ordering`; the incremental-pull framing is orientation, not a separate fact |
| Sample JSON `meta` block | in guide already | `docs/api/index.rst`, Pagination section |
| Base URL (detail) | in spec | path in `location-v2.json` |
| "Create Location" description / base URL | in spec | `Docs.description`, path |
| Required fields `name` / `location_type_code` | belongs in spec | confirmed in `LocationResource.obj_create()` (v0_6.py): raises `LocationAPIError` if either key is absent from the request body. Not previously reflected — `request_schema()` derives no `required` list for this hand-rolled `obj_create` (same generator limitation noted in the user-v1/group-v1 sweeps). **Not added**: adding a bespoke `required` list for one resource would need a new generator mechanism, out of scope for a Docs-text sweep; left as prose-verified-accurate instead of silently dropped (see "considered and rejected" below) |
| `site_code` "system will generate one if not provided. Must be unique on the domain." | belongs in spec | confirmed in `_update()`: `generate_site_code()` called when `'site_code' not in data`; `validate_site_code()` rejects a domain-duplicate. Added to `field_schemas['site_code']['description']` in v0_6.py, regenerated |
| `latitude` / `longitude` (optional, on create) | in spec | properties.\*.description, unchanged from base |
| `location_data` "JSON dictionary instead of a string" | in spec (implicit) | `additionalProperties: true, type: object` in the generated schema already reflects this; no separate prose needed |
| `parent_location_id` "validated to ensure the parent exists, supports child locations, and has no duplicate names" | belongs in spec | confirmed for create: `_get_parent_location()` (existence), `get_location_type()` → `LocationForm.get_allowed_types()` (child-type support), `_validate_unique_among_siblings()` via the always-required `name` branch (no duplicate sibling name). Added to `field_schemas['parent_location_id']['description']` in v0_6.py, regenerated |
| Example Request Body (create) | in spec | illustrates fields already covered above |
| "Update Location" description / base URL | in spec | `Docs.description`, path |
| `name` (PUT) "Must be unique among siblings" | belongs in spec | confirmed in `_update()`: `_validate_unique_among_siblings()` runs whenever `name` is in the request. Added to `field_schemas['name']['description']` in v0_6.py, regenerated |
| `site_code` (PUT) "Must be unique on the domain" | belongs in spec | same `validate_site_code()` call as create; same added description covers both create and update |
| `latitude` / `longitude` (PUT) | in spec | unchanged from create |
| `location_data` (PUT) "Dictionary format" | belongs in spec (expanded) | the page never claimed replace-vs-merge, but the brief calls this out as a live question here (unlike `user_data`, which merges — see below). Confirmed in `_update()`: `setattr(bundle.obj, 'metadata', data.pop('location_data'))` is a wholesale overwrite, not a per-key merge (contrast `UserData.update()`, which only touches submitted keys). Added "this replaces the location's entire custom data — keys not included in the value are removed, not merged" to `field_schemas['location_data']['description']` in v0_6.py, regenerated |
| `location_type_code` (PUT) "the new location type must be a valid child type of that parent" | belongs in spec | confirmed via `get_location_type()` → `allowed_types` check. Added to `field_schemas['location_type_code']['description']` in v0_6.py, regenerated |
| `parent_location_id` (PUT) "parent must exist, be able to have child locations of this type, and must not already have a child with the same name" | belongs in spec (with a correction) | confirmed for update *except* one nuance the old prose did not carry: `_validate_new_parent()` (which does the child-type and duplicate-name checks) only runs `if not is_new_location and 'location_type_code' not in data` — so moving a location to a new parent **while also changing its type in the same request** skips the duplicate-sibling-name check (the type check still happens, via `get_location_type()`). The old unconditional claim was slightly too strong. Added the corrected, narrower wording to `field_schemas['parent_location_id']['description']` in v0_6.py, regenerated |
| "If a part of the location's update fails due to invalid fields, the update will not occur at all" | in spec (implicit) | confirmed in `_update()`: every field is validated and assigned to `bundle.obj` in memory, and `bundle.obj.save()` is the last line — any validation exception raised earlier means `save()` is never reached, so nothing persists. True by construction; no separate prose needed since it is not a distinct rule to violate |
| Example Request Body (update) | in spec | illustrates fields already covered above |
| "Create and Update Locations (in Bulk)" description / base URL (PATCH) | in spec | `Docs.description`, path |
| "Even though the method is PATCH, you can also create locations" | in spec | reflected in `LocationResource.patch_list()` (v0_6.py): dispatches to `obj_create` when `location_id` is absent from an entry, `obj_update` when present |
| `location_id` "include ... to update ... don't include ... to create" | belongs in spec | same `patch_list()` dispatch. Added to `field_schemas['location_id']['description']` in v0_6.py, regenerated |
| "uses the same validation as the create/update endpoint" | in spec (implicit) | `patch_list()` calls the same `obj_create()`/`obj_update()` methods documented above; no separate fact |
| Example Request Body (bulk) | in spec | illustrates fields already covered above |
| "the PATCH request is atomic ... none of the locations will be created or updated" | belongs in spec | confirmed in `LocationResource.patch_list()` (v0_6.py): wrapped in `@atomic`, and the base `patch_list_replica()` (`corehq/apps/api/resources/__init__.py`) only catches `AssertionError` per-item — `LocationAPIError` (a `tastypie.exceptions.BadRequest`) from any one entry is **not** caught there, so it propagates out of the `@atomic` block and rolls back the whole batch. Added to the resource's `Docs.description` (shared across GET/POST/PATCH for this resource, matching the precedent set by the `require_account_confirmation` note on `CommCareUserResource` in the user-v1 sweep), regenerated |

## location-types.rst

| Item | Bucket | Where it went |
| --- | --- | --- |
| "List Location Types" description / base URL | in spec | `Docs.description`, path in `location-type-v1.json` |
| Sample JSON `meta` block | in guide already | `docs/api/index.rst`, Pagination section |
| Sample JSON: `administrative` / `code` / `domain` / `id` / `name` / `parent` / `shares_cases` / `view_descendants` | in spec | `properties.*.description` on `LocationTypeResource` (v0_5.py) |
| Sample JSON: `resource_uri` | in spec | `Docs.field_schemas['resource_uri']` in v0_5.py |
| "Location Type Details" description / base URL | in spec | `Docs.description`, path, `{pk}` operation |
| Detail sample JSON (same fields) | in spec | detail response uses the same object schema as list |

## New cross-cutting facts added to the guide

None. `docs/api/index.rst` already carries Authentication, Pagination and
Response format sections (added by Task 3, corroborated by Tasks 4-7) that
cover everything cross-cutting across these three pages.

## Resource code changed

`corehq/apps/locations/resources/v0_6.py` only (`LocationResource`,
location-v2). No change to `v0_5.py` — location-v1 and location-type-v1
already had every field and endpoint fact captured in `Docs`/`help_text`
before this sweep (all 14 and all 9 items landed "in spec" with zero
promotions), a result of the earlier "Document the location and lookup
table APIs in code" commit (22e82b8480e) on this branch.

## `location_data` replace-vs-merge verdict

**Replaces**, not merges — settled by `LocationResource._update()` in
`corehq/apps/locations/resources/v0_6.py`:
`setattr(bundle.obj, 'metadata', data.pop('location_data'))`. This
assigns the whole submitted dict as the location's `metadata`, the same
wholesale-overwrite shape as `GroupResource`'s `metadata` field in the
group-v1 sweep, and unlike `CommCareUserResource`'s `user_data`, which
`UserData.update()` merges key-by-key. The old locations-v2.rst prose
never actually asserted a merge-vs-replace behavior (grepped for
"replace"/"merge"/"pull... current data" — no match), so there was no
inaccurate claim to correct; this is a new fact promoted into the spec
because the brief flagged it as a live question worth answering from the
code rather than assuming.

## Items considered for promotion and rejected

- **`name`/`location_type_code` "required to create"**: genuinely
  enforced (`obj_create()` raises if either is missing), but the
  generator's `request_schema()` deliberately derives no `required` list
  for hand-rolled `obj_create`/`obj_update` resources (see the comment in
  `corehq/apps/api/openapi/operations.py::request_schema()` and the same
  precedent noted in the user-v1 sweep for `username`). Unlike
  `username` in that sweep, `name`/`location_type_code` are declared
  Tastypie fields already carrying a `description`; there is no
  `required`-shaped hook to add "required to create" to without
  restating the same base description sentence for both fields with
  wording specific to only one HTTP method, so it stayed as accurate
  page prose that the sweep verified rather than an edit to the spec.
  Left off the reduced page anyway (the reduced page is orientation +
  link only, per the sweep procedure's shape), so no inaccurate text
  survives; a future generator enhancement (per the user-v1 precedent)
  is the right place to add real `required` support.
- **`latitude`/`longitude` validity/format constraints**: the field is a
  plain `DecimalField`; no resource code adds range or format validation
  beyond what tastypie itself does, so there was no undocumented
  behavior to add.
- **`location_data` field-name validation against the project's
  location-fields settings**: read `CustomDataFieldsDefinition.get_validator()`
  (`corehq/apps/custom_data_fields/models.py`) — it validates
  `required`/`choices`/`regex` only for fields the project has *defined*,
  and does not reject or drop keys absent from that definition. Neither
  the old page nor the spec ever claimed fields must be predefined or
  that unknown keys are rejected, so there was no claim to fix; adding
  brand-new documentation of this validator's behavior would be adding
  new page content the sweep wasn't asked to write, so left alone.
- **Sample bulk response** (`location_id` `eea759ae08044807be749f665a1fd39a`
  example creating "Newtown" and updating "Springfield"): illustrative
  values only, no claim beyond the fields already covered above.
