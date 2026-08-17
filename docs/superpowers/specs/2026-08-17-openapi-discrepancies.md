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
  fields are ever serialized. Current code cannot emit `path`. The spec keeps a
  `path` field on `Group` (per the task brief) for continuity with the
  documented sample; a human should confirm whether the field was removed from
  the API without updating the docs, or whether the sample output is simply
  stale.
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
- **Validation-error body uses `error_message`, not the `error` key used by
  every other endpoint.** Neither reST page documents an error response
  shape at all for `POST`/`PUT`. `v0_5.GroupResource.serialize`
  (`corehq/apps/api/resources/v0_5.py:662-665`) returns
  `{"error_message": "<detail>"}` for `createGroup` and `replaceGroup` on
  validation failure (e.g. `obj_create`'s `AssertionError` messages at
  `v0_5.py:753` and `:759`; `obj_update`'s at `:764` and `:766`) — this
  differs from the shared `BadRequest`/`Error` schema (`{"error": ...}`) used
  by every other resource's `400`. The bulk `PATCH` path is different again:
  `patch_list_replica` (`corehq/apps/api/resources/__init__.py:172-205`)
  passes a plain list to `serialize`, and `_is_list` short-circuits the
  `error_message` rewrite for `PATCH`, so `bulkUpdateGroups`'s `400` body is
  actually a flat array of strings (ids for successes, raw error text for
  failures), not an object at all. The spec's `createGroup`/`replaceGroup`
  `400` responses now use `error_message`; `bulkUpdateGroups`'s `400` uses a
  string-array schema instead, since copying the `error_message` object shape
  onto it would itself be inaccurate.
- *(append further findings here as they are confirmed)*
