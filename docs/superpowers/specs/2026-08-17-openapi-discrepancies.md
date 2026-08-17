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
- *(append further findings here as they are confirmed)*
