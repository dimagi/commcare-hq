# OpenAPI cross-check: docs vs. code discrepancies

Generated while writing the OpenAPI spec. The spec records what the **code**
does. Each item below is a place where `docs/api/*.rst` disagrees, for human
triage. Nothing here has been changed in the reST docs.

## group/v1 (`list-groups.rst`, `user-group.rst`)

- **Sample output includes a `path` field the code never produces.** Both
  `list-groups.rst:70-83` and `user-group.rst:49-62` show `"path": []` in the
  sample JSON. `v0_4.GroupResource` (`corehq/apps/api/resources/v0_4.py:234-258`)
  declares no `path` field, and the underlying `Group` couch model
  (`corehq/apps/groups/models.py:38-57`) has no `path` property either — `Group`
  is a plain `tastypie.resources.Resource` subclass, so only explicitly declared
  fields are ever serialized. Current code cannot emit `path` under any
  circumstance, so the spec's `Group` schema does not include a `path`
  property, even though both reST samples show one; a human should confirm
  whether the field was removed from the API without updating the docs, or
  whether the sample output is simply stale.
- **`POST` (create) returns only `{"id": ...}`, not a full group.** Docs
  document `name`/`case_sharing`/`reporting`/`users`/`metadata` as *input*
  parameters for the Bulk API's create, but never explicitly state the
  response body is limited to `id` (`user-group.rst:115-126` lists only `id`
  under "Output Parameters", which does match the code, but neither reST
  page states this explicitly as a body-shape contract). `v0_5.GroupResource.
  serialize` (`corehq/apps/api/resources/v0_5.py:662-668`) rewrites the
  response to `{'id': data.obj._id}` whenever `request.method == 'POST'` and
  no `error_message` is present — the full `Group` representation is never
  returned. An integrator following `list-groups.rst`'s sample output (which
  shows a full group object) and assuming `POST` mirrors it would build the
  wrong client. The spec's `createGroup` `201` response now reflects the real
  `{id}`-only shape.
- **`createGroup`'s validation-error body uses `error_message`, not the
  `error` key used by every other endpoint.** Neither reST page documents an
  error response shape at all for `POST`. `v0_5.GroupResource.post_list`
  (`corehq/apps/api/resources/v0_5.py:676-698`) catches `obj_create`'s
  `AssertionError` (raised at `v0_5.py:753` and `:759`, e.g. "Name is
  required") and sets `bundle.data['error_message'] = str(e)` before calling
  `create_response`; `serialize` (`v0_5.py:662-668`) then rewrites the body to
  `{"error_message": "<detail>"}`. This differs from the shared
  `BadRequest`/`Error` schema (`{"error": ...}`) used by every other
  resource's `400`. **Correction (fix round 3):** an earlier version of this
  entry also claimed `replaceGroup` (`PUT`) uses `error_message`, citing
  `obj_update`'s asserts at `v0_5.py:764` and `:766` — that citation was
  wrong. Those are bare `assert bundle.obj.domain == kwargs['domain']`
  statements with no catcher; if they ever fail it's an uncaught
  `AssertionError` producing a 500, not a 400 body, and has nothing to do
  with `error_message`. `replaceGroup`'s real `400` comes from `_update`
  (`v0_5.py:706,710`) raising tastypie's `BadRequest`, which `wrap_view`
  converts to the standard `{"error": ...}` shape
  (`tastypie/resources.py:244-246`) — the same shape the shared `BadRequest`
  response already documents, so there is no discrepancy for `replaceGroup`
  and no schema of its own is needed. The bulk `PATCH` path is different
  again: `patch_list_replica`
  (`corehq/apps/api/resources/__init__.py:172-205`) passes a plain list to
  `serialize`, and `_is_list` short-circuits the `error_message` rewrite for
  `PATCH`, so `bulkUpdateGroups`'s `400` body is actually a flat array of
  strings (ids for successes, raw error text for failures), not an object at
  all (see the next entry). The spec's `createGroup` `400` now uses a named
  `GroupErrorMessage` schema; `replaceGroup`'s `400` uses the shared
  `BadRequest` ref; `bulkUpdateGroups`'s `400` uses a string-array schema.
- **Bulk `PATCH`'s response array mixes ids and error messages
  positionally, with no marker telling them apart.** Undocumented in both
  reST pages (`user-group.rst`'s Bulk API section shows only sample
  *inputs*, no sample output for `PATCH`). `patch_list_replica`
  (`corehq/apps/api/resources/__init__.py:172-205`): for each submitted
  object, on success nothing marks the entry as a ok; on failure
  (`AssertionError`), line 199-201 overwrites that same slot with the error
  text (`bundle.data['_id'] = str(e)`); on success the slot keeps whatever
  id `obj_create`/`obj_update` produced. Line 204 then serializes
  `[bundle.data['_id'] for bundle in bundles_seen]` — one array, same order
  as the request's `objects`, where each element is *either* a new group id
  *or* an error message, and `status` (202 vs. 400) only reports whether
  the batch had zero or at least one failure, not which elements failed. A
  client cannot distinguish success from failure elements except by
  shape-guessing (e.g. does this string look like a group UUID). The spec's
  `bulkUpdateGroups` `202`/`400` responses now describe this explicitly.
- **`replaceGroup` (`PUT` on a missing group) returns a 500, not a 404 —
  likely a genuine bug, not just an undocumented one.** Neither reST page
  states what happens when the `group_id` doesn't exist. `obj_update`
  (`corehq/apps/api/resources/v0_5.py:762-763`) fetches the object with
  `Group.get(kwargs['pk'])`, which raises couchdbkit's `ResourceNotFound` on a
  miss. Tastypie's `put_detail` only catches `(NotFound, MultipleObjectsReturned)`
  (`tastypie/resources.py:1467-1502`) — `ResourceNotFound` is neither
  tastypie's `NotFound` nor Django's `ObjectDoesNotExist`, so it is not
  caught there. It propagates to `wrap_view`'s generic `except Exception`
  (`tastypie/resources.py:250-260`) and `get_response_class_for_exception`
  (`tastypie/resources.py:273-284`) does not recognize it either, so the
  response is `http.HttpApplicationError` — a 500. Contrast `getGroup`/
  `deleteGroup`, whose `obj_get` uses `get_object_or_not_exist`
  (`corehq/apps/api/util.py:15-39`), which raises Django's
  `ObjectDoesNotExist` and does get mapped to a real 404. The spec's
  `replaceGroup` operation deliberately omits `404` (with an inline YAML
  comment explaining why, in `paths/group.yaml`) rather than document a
  response the code cannot produce. A human should decide whether to fix
  `obj_update` to raise something tastypie's `put_detail`/`_handle_500`
  recognizes as "not found."
- **`getGroup`'s and `deleteGroup`'s 404s both reach status 404, by two
  different mechanisms, with two different bodies -- neither matches the
  shared `NotFound` response's `{"error": ...}` shape (fix round 4, in
  response to a concern raised while fixing the `replaceGroup` finding
  above).** Neither reST page documents a 404 body shape at all.
  - `getGroup` (`GET`) uses tastypie's own `get_detail`
    (`tastypie/resources.py:1362-1383`), which catches `ObjectDoesNotExist`
    directly and returns a bare `http.HttpNotFound()` -- a plain
    `HttpResponse` built without going through `serialize`/`error_response`
    at all. **The body is empty.** The spec's `getGroup` `404` no longer
    points at the shared `NotFound` ref; it documents an empty body instead.
  - `deleteGroup` (`DELETE`) uses `delete_detail`
    (`tastypie/resources.py:1525-1541`), which only catches tastypie's own
    `NotFound` exception -- but `obj_delete` -> `obj_get`
    (`v0_4.py:246-247`, `get_object_or_not_exist`,
    `corehq/apps/api/util.py:15-39`) raises Django's `ObjectDoesNotExist`
    instead, which `delete_detail` does not catch. It propagates to
    `wrap_view`'s generic exception handler, `_handle_500`
    (`tastypie/resources.py:265-292`), which maps `ObjectDoesNotExist` to a
    404 status via `get_response_class_for_exception` but builds the body
    itself: `{"error_message": "Sorry, this request could not be processed.
    Please try again later."}` in production (a canned message, not
    resource-specific; `settings.TASTYPIE_CANNED_ERROR` is not overridden
    anywhere in this codebase) or `{"error_message": "<real message>",
    "traceback": ...}` under `DEBUG`. **The body is JSON, but keyed
    `error_message`, not `error`, and the message is generic.** The spec's
    `deleteGroup` `404` now uses the `GroupErrorMessage` schema instead of
    the shared `NotFound` ref.
  - A general comment was added to `components/responses.yaml`'s `NotFound`
    entry warning that its `{"error": ...}` body only holds where a resource
    actually renders one, and that later resource tasks must verify each
    detail operation's real 404 shape rather than reach for this ref by
    default.
- *(append further findings here as they are confirmed)*
