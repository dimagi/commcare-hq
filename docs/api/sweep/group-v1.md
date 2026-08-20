# Sweep: group-v1

Source pages:
- `docs/api/user-group.rst` (233 lines at 5bad60283a0)
- `docs/api/list-groups.rst` (83 lines at 5bad60283a0)

Reference URL: `/api/docs/group-v1/`. Coverage 8/8 (`case_sharing`, `domain`,
`id`, `metadata`, `name`, `reporting`, `resource_uri`, `users`) — all response
fields are described in the spec under `GroupResource`
(`corehq/apps/api/resources/v0_4.py`, extended by `v0_5.py`).

## list-groups.rst

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose paragraph (CHW health-district example) | rewritten | new orientation sentence on the reduced page |
| Base URL | in spec | path in group-v1.json |
| Authentication note + wiki link | in guide already | `docs/api/index.rst`, Authentication section |
| Permission Required ("Edit Mobile Workers") | in spec | `Docs.description`, "Requires the `edit_commcare_users` permission." |
| Input param `format` | in spec / in guide already | group-v1.json GET parameters, `format`; also `docs/api/index.rst`, Response format section |
| Output `id` | in spec | properties.id.description |
| Output `name` | in spec | properties.name.description |
| Sample Usage URL | in spec | same base URL as above |
| Sample JSON `meta` block | in guide already | `docs/api/index.rst`, Pagination section |
| Sample JSON `case_sharing` | in spec | properties.case_sharing.description |
| Sample JSON `domain` | in spec | properties.domain.description |
| Sample JSON `metadata` | in spec | properties.metadata.description |
| Sample JSON `path: []` | obsolete | `Group` (`corehq/apps/groups/models.py`) has no `path` property, and `GroupResource` declares no `path` field — nothing produces this key. Not part of the actual response. Removed. |
| Sample JSON `reporting` | in spec | properties.reporting.description |
| Sample JSON `users` | in spec | properties.users.description |
| Sample JSON (missing) `resource_uri` | n/a | the sample predates this field being added to the resource; not a claim to carry forward, just a stale example |

## user-group.rst

### List Groups (GET .../group/v1/) — duplicate of list-groups.rst

| Item | Bucket | Where it went |
| --- | --- | --- |
| Base URL, Authentication, Permissions, `format` param, Sample Output | in spec / in guide already | same rows as list-groups.rst above; this section is a near-duplicate of that page |

### Bulk API (POST / PATCH .../group/v1/)

| Item | Bucket | Where it went |
| --- | --- | --- |
| URL, Supported Methods (POST create, PATCH create multiple) | in spec | paths in group-v1.json; PATCH dispatches to `obj_create` per object via `patch_list_replica()`, confirmed in `GroupResource.patch_list()` (`corehq/apps/api/resources/v0_5.py`) |
| `name*` required | belongs in spec | not previously reflected in the schema (no `required` list is emitted for this hand-rolled `obj_create`, matching the precedent noted in Task 4's checklist for `operations.py::request_schema()`). Confirmed in `GroupResource.obj_create()` (v0_5.py): raises `AssertionError("Name is required")` when blank. Added to `field_schemas['name']['description']` in v0_4.py, regenerated. |
| `name` must be unique within the domain | belongs in spec | confirmed in the same `obj_create()`: raises `AssertionError("A group with name %s already exists")` when `Group.by_name()` finds a match. Added to the same `name` description above, regenerated. |
| `case_sharing` meaning + default | in spec | properties.case_sharing.description, default `false` |
| `reporting` meaning + default | in spec | properties.reporting.description, default `true` |
| `users` "optional to specify" | in spec | field is not marked required in the generated request schema; optionality already reflected structurally |
| `metadata` "optional to specify" | in spec | field is `nullable: true` in the generated request schema |
| Output `id` | in spec | properties.id.description |
| Sample Input (single group) / Sample Input (multiple groups) JSON blocks | in spec | illustrate fields already covered above; no new claims |

### Individual API (GET / PUT / DELETE .../group/v1/{group_id}/)

| Item | Bucket | Where it went |
| --- | --- | --- |
| URL, Supported Methods (GET/PUT/DELETE) | in spec | paths in group-v1.json |
| `name` (PUT) | in spec | properties.name.description; renaming to a name already in use by another group, or to a blank name, is also covered by the `name` addition above — confirmed in `GroupResource._update()` (v0_5.py), which raises `BadRequest` for both cases |
| `case_sharing` (PUT) | in spec | properties.case_sharing.description |
| `reporting` (PUT) | in spec | properties.reporting.description |
| `users` (PUT) "this will replace any existing users for the group" | belongs in spec | confirmed in `GroupResource._update()` (v0_5.py): computes the set difference between the current membership and the submitted list, adds the missing users and removes the extras — the end result is the group's membership matching the submitted list exactly. Added to `field_schemas['users']['description']` in v0_4.py, regenerated. |
| `metadata` (PUT) "this will replace any existing custom data for the group" | belongs in spec | checked against the code, unlike the analogous mobile-worker `user_data` claim (which turned out to be false, per Task 4). Confirmed accurate here: `GroupResource._update()` does a plain `setattr(bundle.obj, 'metadata', value)` for a `metadata` key present in the request body — a wholesale replace, not a per-key merge like `UserData.update()`. Added to `field_schemas['metadata']['description']` in v0_4.py, regenerated. |
| Sample Input JSON block | in spec | illustrates fields already covered above; no new claims |

## New cross-cutting facts added to the guide

None. `docs/api/index.rst` already carries Authentication, URL structure,
Pagination and Response format sections (added by Task 3 and corroborated
by Task 4) that cover everything cross-cutting on these two pages.

## Items considered for promotion and rejected

- **`format` query parameter**: already promoted to the guide during Task 4
  (corroborated across `list-mobile-workers.rst`, `list-groups.rst` and
  `user-group.rst`); no further action needed here.
- **Permission name "Edit Mobile Workers"**: considered adding a note to the
  guide that group management rides on the mobile-worker-editing permission
  rather than a groups-specific one, but this is a fact about one resource's
  authorization, not about the APIs collectively, so it stays as the
  operation-level `Docs.description` text already in the spec.
- **`metadata` "replaces existing data" claim**: this is the one item on
  this page that matches the shape of the known-bad claim on
  `mobile-worker.rst` (a PUT described as replacing a JSON blob). It was
  checked against `GroupResource._update()` rather than assumed correct —
  and, unlike the mobile-worker case, it held up: the code really does
  overwrite the whole `metadata` value with whatever is sent, with no
  per-key merge. Promoted to the spec instead of being reclassified as
  obsolete.
