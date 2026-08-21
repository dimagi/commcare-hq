# Sweep: form-v1

Source pages:
- `docs/api/list-forms.rst` (181 lines at 5bad60283a0)
- `docs/api/form-data.rst` (135 lines at 5bad60283a0)

Reference URL: `/api/docs/form-v1/`. Coverage 22/22.

Most `XFormInstanceResource` field/parameter descriptions were already
written into `corehq/apps/api/resources/v0_4.py` and regenerated in an
earlier commit on this branch (`ab8db28fb65`, "Document the case, form and
group APIs in code"), including a correction that `appVersion` filtering is
accepted but never matches (ES mapping mismatch). This sweep re-verifies
that work against the two RST pages and finds one field the earlier pass
missed (`limit`'s maximum), plus the form-data-specific items.

## list-forms.rst

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose sentence | rewritten | new orientation sentence on the reduced page |
| Base URL | in spec | path in form-v1.json |
| Authentication note + wiki link | in guide already | `docs/api/index.rst`, Authentication section |
| Permission Required ("Edit Data") | in spec | `Docs.description`, "Requires the `edit_data` permission." |
| Input param `xmlns` | in spec | properties/parameters, `xmlns` |
| Input param `limit` "Default: 20. Maximum: 1000" | belongs in spec | default was already generated from `Meta.limit`/tastypie default, but the numeric cap was not stated. Confirmed `XFormInstanceResource.Meta` sets no `max_limit`, so tastypie's `ResourceOptions.max_limit = 1000` (`tastypie/resources.py`) applies, and `Paginator.get_limit()` clamps silently rather than erroring. Added a resource-level `limit` parameter override (description + max) to `Docs.parameters` in `v0_4.py` so it doesn't affect other resources with a different `max_limit` (e.g. `CommCareCaseResource` sets 5000). Regenerated. |
| Input param `offset` | in spec / in guide already | form-v1.json parameter; generic behavior already in `docs/api/index.rst` Pagination section |
| Input param `indexed_on_start` / `indexed_on_end` | in spec | parameters, same names |
| Input param `received_on_start` / `received_on_end` | in spec | parameters, same names |
| Input param `appVersion` | in spec (corrected) | already documented as non-functional in `Docs.parameters` from the earlier commit; verified against `es_query_from_get_params()` and `xform_mapping.py` — the old RST claim that this filter works is wrong, and the spec's existing text says so |
| Input param `include_archived` | in spec | parameters, `include_archived` |
| Input param `app_id` | in spec | parameters, `app_id` |
| Input params `indexed_on` / `server_modified_on` / `received_on` (sort orders) | in spec | `order_by` parameter, generated enum from `Meta.ordering` |
| Input param `case_id` | in spec | parameters, `case_id` |
| Sample Usage URL | in spec | same base URL as above |
| Sample JSON `meta` block | in guide already | `docs/api/index.rst`, Pagination section |
| Sample JSON per-field meanings (`app_id`, `archived`, `attachments`, `build_id`, `domain`, `form`, `id`, `initial_processing_complete`, `is_phone_submission`, `metadata`, `problem`, `received_on`, `resource_uri`, `server_modified_on`, `type`, `uiversion`, `version`) | in spec | properties.\*.description, all present |
| Sample JSON `resource_uri: ""` | n/a | stale example value (the real response is non-empty, as shown in the regenerated example); not a claim to carry forward |

## form-data.rst (content above the Form Attachments section)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose paragraph | rewritten | new orientation sentence |
| Single Form URL | in spec | path in form-v1.json |
| Authentication note + wiki link | in guide already | `docs/api/index.rst`, Authentication section |
| Sample URL | in spec | same base path as list-forms |
| Sample JSON field meanings (`app_id`, `archived`, `build_id`, `form`, `id`, `metadata`, `received_on`, `resource_uri`, `type`, `uiversion`, `version`) | in spec | properties.\*.description, all present |
| Sample JSON `md5: "OBSOLETED"` | obsolete | `XFormInstanceResource` declares no `md5` field and nothing in `dehydrate()` adds one; grepped `v0_3.py`/`v0_4.py` for `md5` with no match. Not part of the actual response. Removed. |

## Form Attachments section — no spec at all

| Item | Bucket | Where it went |
| --- | --- | --- |
| Entire "Form Attachments" section (lines 102-135 of the original `form-data.rst`) | no spec — retained verbatim | `get_form_attachment_response` in `corehq/apps/reports/views.py` is a plain Django view, not a tastypie resource, and is not in the OpenAPI generator's catalogue — there is nothing to link to. This is the only documentation this endpoint has, so it is kept byte-for-byte identical on the reduced page rather than deleted or reduced. Verified: `tail -n 34 docs/api/form-data.rst \| sha256sum` = `e31cbc60f8eda5d4e9cf8aa719c6aed7c91337a7f1cb5eec136e1fbf8ef92c3e`, matching the section before this sweep. |

## New cross-cutting facts added to the guide

None. `docs/api/index.rst` already carries Authentication and Pagination
sections that cover everything cross-cutting on these two pages.

## Items considered for promotion and rejected

- **`offset` default of 0**: already generated centrally by
  `standard_list_parameters()` in `corehq/apps/api/openapi/operations.py`
  and shared across every list resource; nothing form-specific to add.
- **`resource_uri` empty-string sample value**: considered flagging as
  obsolete/inaccurate like the mobile-worker precedent, but this is a
  stale illustrative value in an example the whole sample block is being
  removed for, not a standalone claim being carried forward — no separate
  action needed.
- **`case_id` "will only return forms which updated that case"**: checked
  against `es_query_from_get_params()` filtering on `case_id`; behavior
  matches the existing spec description exactly, already "in spec".
