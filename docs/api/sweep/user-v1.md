# Sweep: user-v1

Source pages:
- `docs/api/list-mobile-workers.rst` (212 lines at b6e5a14f14f)
- `docs/api/mobile-worker.rst` (313 lines at b6e5a14f14f)

Reference URL: `/api/docs/user-v1/`. Coverage re-confirmed 18/18 under Task
2's stricter count before starting.

## Precedent check (done first, per brief)

The three constraints `mobile-worker.rst` was previously (and once
incompletely) rescued for are present, but **only at the operation-level
`description`**, not in the individual field descriptions — checking field
descriptions alone (`password`: "The user's password...", `email`: "Email
address of user.", `phone_numbers`: "List of all phone numbers of the
user.") makes it look like two of three are missing. Verified in
`docs/api/spec/user-v1.json`, `paths./a/{domain}/api/user/v1/.post.description`
(and the same text on the other operations for this resource):

> "When `require_account_confirmation` is set, `password` must be omitted
> (the user sets their own password on confirmation) and `email` must be
> provided (the confirmation is sent there). When `phone_numbers` is sent,
> its first entry becomes the mobile worker's `default_phone_number`."

All three confirmed present. No re-rescue needed for these three.

## list-mobile-workers.rst

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose sentence | in guide (rewritten) | new orientation sentence on the reduced page |
| Base URL / Single User URL | in spec | paths in user-v1.json |
| Permissions Required (both occurrences) | in spec | v0_5.py `Docs.description`, "Requires the `edit_commcare_users` permission." |
| "Authentication and Usage" / cURL note, link to API Authentication wiki page | in guide already | `docs/api/index.rst`, Authentication section |
| Input param `format` | in spec | user-v1.json, GET parameters, `format` |
| Input param `group` | in spec | user-v1.json, GET parameters, `group` |
| Input param `archived` | in spec | user-v1.json, GET parameters, `archived` |
| Input param `extras` | in spec | user-v1.json, GET parameters, `extras` |
| Output `id` | in spec | properties.id.description |
| Output `username` | in spec | properties.username.description |
| Output `first_name` / `last_name` | in spec | meaning exhausted by name, properties.\*.description |
| Output `default_phone_number` | in spec | properties.default_phone_number.description |
| Output `email` | in spec | properties.email.description |
| Output `phone_numbers` | in spec | properties.phone_numbers.description |
| Output `groups` | in spec | properties.groups.description |
| Output `primary_location` | in spec | properties.primary_location.description |
| Output `locations` | in spec | properties.locations.description |
| Output `user_data` | belongs in spec | field meaning ("any additional custom data") was already in spec, but the note "(if the property begins with a number, it will not be returned when using XML)" was not — verified accurate against `CommCareUserResource.dehydrate_user_data()` in `corehq/apps/api/resources/v0_1.py`, which drops digit-leading keys only when the response format is XML. Added to `field_schemas['user_data']['description']` in `corehq/apps/api/resources/v0_5.py`, regenerated. |
| Sample JSON: `type: "user"` field | obsolete | `type = "user"` in `v0_1.UserResource` is a plain class attribute, not a declared Tastypie `ApiField`; Tastypie's declarative metaclass only serializes declared fields, and no `dehydrate_type`/override adds it back. It is not part of the actual response. No spec entry exists for it and none should be added. Removed from the reduced page. |
| Sample JSON: `resource_uri` | in spec | properties.resource_uri.description ("URI of this record in the API.") |
| Sample JSON `meta` block (limit/offset/next/previous/total_count) | in guide already | `docs/api/index.rst`, Pagination section |
| Sample Usage (`?format=xml&limit=5`) | in spec / in guide already | URL structure from index.rst URL structure section; `format`/`limit` params documented in spec |
| Sample XML Output block | in spec (same fields as JSON) | same field descriptions apply regardless of serialization; XML-specific digit-key note handled under `user_data` above |

## mobile-worker.rst

### User Creation (POST)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose sentence | rewritten | new orientation sentence |
| Permissions Required | in spec | `Docs.description`, "Requires the `edit_commcare_users` permission." |
| URL / Method | in spec | paths in user-v1.json |
| `username*` required | belongs in spec | not previously reflected anywhere in the generated schema (the generator deliberately does not derive `required` for hand-rolled `obj_create`/`obj_update` resources — see the comment in `corehq/apps/api/openapi/operations.py::request_schema()`). Added "Required to create a mobile worker." to `field_schemas['username']['description']` in v0_5.py, regenerated. |
| `password*` required (conditionally) | in spec | already covered by `password`'s own description: "Required unless connect_username is provided, or unless require_account_confirmation is set...". Verified in `field_schemas['password']['description']`, pre-existing. |
| `first_name` / `last_name` | in spec | meaning exhausted by name |
| `email` | in spec | properties.email.description |
| `phone_numbers` incl. "first one becomes default" | in spec | this is one of the three precedent constraints — operation-level `Docs.description` (see above) |
| `groups` | in spec | properties.groups.description |
| `user_data` | in spec | properties.user_data.description (rescued XML digit-key note under list-mobile-workers row above applies equally here) |
| `language` | in spec | `field_schemas['language']['description']` (write-only) |
| `primary_location` "must be one of the locations" | belongs in spec | cross-field validation confirmed in `UserUpdates._validate_locations()` (`corehq/apps/api/user_updates.py`): raises if `primary_location` not in `locations`, and if only one of the two is given. Added to `field_schemas['primary_location']['description']`, regenerated. |
| `locations` | in spec | properties.locations.description |
| `require_account_confirmation` | in spec | one of the three precedent constraints, operation-level description |
| `send_confirmation_email_now` | in spec | properties.send_confirmation_email_now.description |
| "\* To send a confirmation email: password excluded, email included, require_account_confirmation=True" | in spec | restates the same precedent constraints already verified at operation level |
| Output `id` | in spec | properties.id.description |
| Sample Input / Sample Input - Unconfirmed User JSON blocks | in spec | illustrate fields already covered above; no new claims |

### User Edit (PUT)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose / Permissions / URL / Method | in spec | as above |
| "Authentication" note + wiki link | in guide already | `docs/api/index.rst`, Authentication section |
| Request Header "Content-Type: application/json" | in spec (implicit) | the operation's `requestBody.content` is keyed on `application/json` in the generated schema; not promoted separately since it isn't corroborated as a cross-cutting fact by any other page (`grep -l Content-Type docs/api/*.rst` matches only this page) |
| `first_name` / `last_name` / `email` / `language` | in spec | unchanged from create |
| `phone_numbers` "(replaces existing ones)" | belongs in spec | confirmed in `CommcareUserUpdates._update_phone_numbers()` (`corehq/apps/api/user_updates.py`): resets `user.phone_numbers = []` then re-adds every value sent — a genuine full-replace, not a merge. Added to `field_schemas['phone_numbers']['description']`, regenerated. |
| `groups` "(replaces existing groups)" | belongs in spec | confirmed in `CommcareUserUpdates._update_groups()`: calls `user.set_groups(group_ids)`, a full replace. Added to `field_schemas['groups']['description']`, regenerated. |
| `user_data` "(replaces existing custom data)" + advice to pull current data first | obsolete (inaccurate as written) | checked `UserData.update()` (`corehq/apps/users/user_data.py`): it merges — only keys present in the request are overwritten; existing keys not mentioned are left untouched. It is not a full replace, so the "advised to pull the user's current data first" caveat, written on the premise that PUT overwrites everything, does not describe current behavior. Removed; no replacement needed since the merge behavior does not carry the risk the advice was warning about. |
| link to `list-mobile-workers.rst` "single user URL" for pulling current data | obsolete | tied to the user_data advice above, which no longer applies; also would have been a `:doc:` cross-reference the brief asks to avoid |
| `password` "New password for user" | in spec | properties.password.description |
| `primary_location` "must be one of the locations", "pass empty string to remove" | belongs in spec | same cross-field validation as the create-side row above, plus confirmed in `UserUpdates._update_location()`: when both `primary_location` and `locations` are falsy, `_remove_all_locations()` runs. Added to `field_schemas['primary_location']['description']`, regenerated. |
| `locations` "pass empty array to remove all" | belongs in spec | same `_update_location()` mechanism as above. Added to `field_schemas['locations']['description']`, regenerated. |
| `send_confirmation_email_now` "if True and user is unconfirmed, sends email" | belongs in spec | confirmed in `CommCareUserResource.obj_update()` (`corehq/apps/api/resources/v0_5.py`): raises `BadRequest` if the account is already confirmed or has no email when this flag is set on update. Added to `field_schemas['send_confirmation_email_now']['description']`, regenerated. |
| Sample Input JSON block | in spec | illustrates fields already covered above |

### User Delete (DELETE)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose / Permissions / URL / Method | in spec | as above |
| "Authentication" note + wiki link | in guide already | `docs/api/index.rst`, Authentication section |

### Send Password Reset Email (POST .../email_password_reset/)

| Item | Bucket | Where it went |
| --- | --- | --- |
| Purpose / Permissions / URL / Method | in spec | `Docs.extra_operations` entry, "Send the mobile worker a password reset email." |
| "Request Body: Empty" | in spec (implicit) | operation has no `requestBody` in the generated schema |
| "Success: HTTP 202 Accepted with empty body" | in spec | operation's `202` response, "The request was accepted." |

## New cross-cutting fact added to the guide

- `docs/api/index.rst` gained a "Response format" subsection: many endpoints
  accept `?format=xml` in addition to the default JSON. This was present on
  `list-mobile-workers.rst` and corroborated as cross-cutting by
  `list-groups.rst`, `cases-v1.rst` and `user-group.rst` (none of which were
  otherwise touched), so it belongs in the guide rather than being
  duplicated per page.

## Items considered for promotion and rejected

- **`format`/`extras`/`archived`/`group` query params**: considered for the
  guide (they look like generic list-endpoint knobs) but `extras` and
  `archived` are resource-specific (mobile-worker activity stats,
  deactivated-user filtering) and `group` is resource-specific too — only
  `format` is genuinely shared across pages, so only that one moved.
- **"Content-Type: application/json" request header note**: considered for
  the guide as a general write-endpoint fact, but no other page states it
  (`grep -l Content-Type docs/api/*.rst` = only this page), so there is no
  corroboration it is cross-cutting; left as implicit in the spec's
  `requestBody` content type instead of guessing.
- **`user_data` "replaces existing data" advice**: considered moving to the
  spec as a caveat, but investigation showed the code does not replace —
  it merges. Reclassified as obsolete instead of being carried forward
  inaccurately.
