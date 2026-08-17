# OpenAPI cross-check: docs vs. code discrepancies

Generated while writing the OpenAPI spec. The spec records what the **code**
does. Each item below is a place where `docs/api/*.rst` disagrees, for human
triage. Nothing here has been changed in the reST docs.

## group/v1 (`list-groups.rst`, `user-group.rst`)

- **Sample output includes a `path` field the code never produces.** Both
  `list-groups.rst:70-83` and `user-group.rst:49-62` show `"path": []` in the
  sample JSON. `v0_4.GroupResource`
  (`corehq/apps/api/resources/v0_4.py:234-258`) declares no `path` field, and
  the underlying `Group` couch model (`corehq/apps/groups/models.py:38-57`) has
  no `path` property either — `Group` is a plain `tastypie.resources.Resource`
  subclass, so only explicitly declared fields are ever serialized. Current code
  cannot emit `path` under any circumstance, so the spec's `Group` schema does
  not include a `path` property, even though both reST samples show one; a human
  should confirm whether the field was removed from the API without updating the
  docs, or whether the sample output is simply stale.
- **`POST` (create) returns only `{"id": ...}`, not a full group.** Docs
  document `name`/`case_sharing`/`reporting`/`users`/`metadata` as _input_
  parameters for the Bulk API's create, but never explicitly state the response
  body is limited to `id` (`user-group.rst:115-126` lists only `id` under
  "Output Parameters", which does match the code, but neither reST page states
  this explicitly as a body-shape contract). `v0_5.GroupResource. serialize`
  (`corehq/apps/api/resources/v0_5.py:662-668`) rewrites the response to
  `{'id': data.obj._id}` whenever `request.method == 'POST'` and no
  `error_message` is present — the full `Group` representation is never
  returned. An integrator following `list-groups.rst`'s sample output (which
  shows a full group object) and assuming `POST` mirrors it would build the
  wrong client. The spec's `createGroup` `201` response now reflects the real
  `{id}`-only shape.
- **`createGroup`'s validation-error body uses `error_message`, not the `error`
  key used by every other endpoint.** Neither reST page documents an error
  response shape at all for `POST`. `v0_5.GroupResource.post_list`
  (`corehq/apps/api/resources/v0_5.py:676-698`) catches `obj_create`'s
  `AssertionError` (raised at `v0_5.py:753` and `:759`, e.g. "Name is required")
  and sets `bundle.data['error_message'] = str(e)` before calling
  `create_response`; `serialize` (`v0_5.py:662-668`) then rewrites the body to
  `{"error_message": "<detail>"}`. This differs from the shared
  `BadRequest`/`Error` schema (`{"error": ...}`) used by every other resource's
  `400`. **Correction (fix round 3):** an earlier version of this entry also
  claimed `replaceGroup` (`PUT`) uses `error_message`, citing `obj_update`'s
  asserts at `v0_5.py:764` and `:766` — that citation was wrong. Those are bare
  `assert bundle.obj.domain == kwargs['domain']` statements with no catcher; if
  they ever fail it's an uncaught `AssertionError` producing a 500, not a 400
  body, and has nothing to do with `error_message`. `replaceGroup`'s real `400`
  comes from `_update` (`v0_5.py:706,710`) raising tastypie's `BadRequest`,
  which `wrap_view` converts to the standard `{"error": ...}` shape
  (`tastypie/resources.py:244-246`) — the same shape the shared `BadRequest`
  response already documents, so there is no discrepancy for `replaceGroup` and
  no schema of its own is needed. The bulk `PATCH` path is different again:
  `patch_list_replica` (`corehq/apps/api/resources/__init__.py:172-205`) passes
  a plain list to `serialize`, and `_is_list` short-circuits the `error_message`
  rewrite for `PATCH`, so `bulkUpdateGroups`'s `400` body is actually a flat
  array of strings (ids for successes, raw error text for failures), not an
  object at all (see the next entry). The spec's `createGroup` `400` now uses a
  named `GroupErrorMessage` schema; `replaceGroup`'s `400` uses the shared
  `BadRequest` ref; `bulkUpdateGroups`'s `400` uses a string-array schema.
- **Bulk `PATCH`'s response array mixes ids and error messages positionally,
  with no marker telling them apart.** Undocumented in both reST pages
  (`user-group.rst`'s Bulk API section shows only sample _inputs_, no sample
  output for `PATCH`). `patch_list_replica`
  (`corehq/apps/api/resources/__init__.py:172-205`): for each submitted object,
  on success nothing marks the entry as a ok; on failure (`AssertionError`),
  line 199-201 overwrites that same slot with the error text
  (`bundle.data['_id'] = str(e)`); on success the slot keeps whatever id
  `obj_create`/`obj_update` produced. Line 204 then serializes
  `[bundle.data['_id'] for bundle in bundles_seen]` — one array, same order as
  the request's `objects`, where each element is _either_ a new group id _or_ an
  error message, and `status` (202 vs. 400) only reports whether the batch had
  zero or at least one failure, not which elements failed. A client cannot
  distinguish success from failure elements except by shape-guessing (e.g. does
  this string look like a group UUID). The spec's `bulkUpdateGroups` `202`/`400`
  responses now describe this explicitly.
- **`replaceGroup` (`PUT` on a missing group) returns a 500, not a 404 — likely
  a genuine bug, not just an undocumented one.** Neither reST page states what
  happens when the `group_id` doesn't exist. `obj_update`
  (`corehq/apps/api/resources/v0_5.py:762-763`) fetches the object with
  `Group.get(kwargs['pk'])`, which raises couchdbkit's `ResourceNotFound` on a
  miss. Tastypie's `put_detail` only catches
  `(NotFound, MultipleObjectsReturned)` (`tastypie/resources.py:1467-1502`) —
  `ResourceNotFound` is neither tastypie's `NotFound` nor Django's
  `ObjectDoesNotExist`, so it is not caught there. It propagates to
  `wrap_view`'s generic `except Exception` (`tastypie/resources.py:250-260`) and
  `get_response_class_for_exception` (`tastypie/resources.py:273-284`) does not
  recognize it either, so the response is `http.HttpApplicationError` — a 500.
  Contrast `getGroup`/ `deleteGroup`, whose `obj_get` uses
  `get_object_or_not_exist` (`corehq/apps/api/util.py:15-39`), which raises
  Django's `ObjectDoesNotExist` and does get mapped to a real 404. The spec's
  `replaceGroup` operation deliberately omits `404` (with an inline YAML comment
  explaining why, in `paths/group.yaml`) rather than document a response the
  code cannot produce. A human should decide whether to fix `obj_update` to
  raise something tastypie's `put_detail`/`_handle_500` recognizes as "not
  found."
- **`getGroup`'s and `deleteGroup`'s 404s both reach status 404, by two
  different mechanisms, with two different bodies -- neither matches the shared
  `NotFound` response's `{"error": ...}` shape (fix round 4, in response to a
  concern raised while fixing the `replaceGroup` finding above).** Neither reST
  page documents a 404 body shape at all.
  - `getGroup` (`GET`) uses tastypie's own `get_detail`
    (`tastypie/resources.py:1362-1383`), which catches `ObjectDoesNotExist`
    directly and returns a bare `http.HttpNotFound()` -- a plain `HttpResponse`
    built without going through `serialize`/`error_response` at all. **The body
    is empty.** The spec's `getGroup` `404` no longer points at the shared
    `NotFound` ref; it documents an empty body instead.
  - `deleteGroup` (`DELETE`) uses `delete_detail`
    (`tastypie/resources.py:1525-1541`), which only catches tastypie's own
    `NotFound` exception -- but `obj_delete` -> `obj_get` (`v0_4.py:246-247`,
    `get_object_or_not_exist`, `corehq/apps/api/util.py:15-39`) raises Django's
    `ObjectDoesNotExist` instead, which `delete_detail` does not catch. It
    propagates to `wrap_view`'s generic exception handler, `_handle_500`
    (`tastypie/resources.py:265-292`), which maps `ObjectDoesNotExist` to a 404
    status via `get_response_class_for_exception` but builds the body itself:
    `{"error_message": "Sorry, this request could not be processed. Please try again later."}`
    in production (a canned message, not resource-specific;
    `settings.TASTYPIE_CANNED_ERROR` is not overridden anywhere in this
    codebase) or `{"error_message": "<real message>", "traceback": ...}` under
    `DEBUG`. **The body is JSON, but keyed `error_message`, not `error`, and the
    message is generic.** The spec's `deleteGroup` `404` now uses the
    `GroupErrorMessage` schema instead of the shared `NotFound` ref.
  - A general comment was added to `components/responses.yaml`'s `NotFound`
    entry warning that its `{"error": ...}` body only holds where a resource
    actually renders one, and that later resource tasks must verify each detail
    operation's real 404 shape rather than reach for this ref by default.
- _(append further findings here as they are confirmed)_

## case/v1 (`cases-v1.rst`)

- **The "Output Values" table for the list endpoint documents the wrong shape
  for JSON responses -- it actually describes the custom XML serialization.**
  `cases-v1.rst:108-146` lists `case_id`, `username`, `user_id`, `owner_id`,
  `case_name`, `external_id`, `case_type`, `date_opened`, `date_modified`,
  `closed`, `date_closed` as if all were top-level response fields.
  `v0_3.CommCareCaseResource` and `v0_4.CommCareCaseResource`
  (`corehq/apps/api/resources/v0_3.py:19-41`,
  `corehq/apps/api/resources/v0_4.py:186-218`) are plain
  `tastypie. resources.Resource` subclasses, so (as with the group resource)
  only explicitly declared class attributes are ever serialized. Of that list,
  only `case_id`/`id`, `user_id`, `date_modified`, `closed`, and `date_closed`
  are declared as top-level fields. `owner_id`, `case_name`, `case_type`,
  `date_opened`, and `external_id` are never top-level -- they only exist nested
  inside the `properties` dict, produced by
  `ESCase.get_properties_in_api_format` (`corehq/apps/api/models.py: 201-212`),
  which the JSON sample two sections later (`cases-v1.rst:179-204`) actually
  shows correctly. `username` is not declared as a field anywhere on either
  class and never appears in JSON output at all -- it only exists in the custom
  XML output built by `CaseToXMLMixin.to_xml`
  (`corehq/form_processor/models/mixin.py:19-29`), which is what the Output
  Values table is really describing (it matches the "Sample XML Output" at
  `cases-v1.rst:158-171`, not the "Sample JSON Output" a few lines later). The
  spec's `Case` schema follows the real JSON shape:
  `owner_id`/`case_name`/`case_type`/`date_opened`/ `external_id` are documented
  as members of `properties`, and `username` is omitted entirely.
- **The sample JSON output includes a `version` field the case resource never
  emits.** `cases-v1.rst:181-201` shows `"version": "1.0"` at the top level of a
  case object. Neither `v0_3.CommCareCaseResource` nor
  `v0_4.CommCareCaseResource` declares a `version` field -- the only `version`
  field in `corehq/apps/api/resources/v0_4.py` belongs to
  `XFormInstanceResource` (line 76), an unrelated resource. The spec's `Case`
  schema has no `version` property.
- **`indexed_on`, `opened_by`, and `closed_by` are real top-level fields the
  docs never mention.** Declared at `corehq/apps/api/resources/ v0_4.py:213-218`
  (`indexed_on` is also the field the docs recommend for pagination, via
  `indexed_on_start`/`indexed_on_end` -- so it is doubly strange it is absent
  from the Output Values table). The spec's `Case` schema includes all three,
  with a note that they are undocumented.
- **The `properties=all`/`indices=all` "Proposed" flags do nothing --
  `properties` and `indices` are always present, unconditionally.**
  `cases-v1.rst:244-253` lists `properties` and `indices` as detail- endpoint
  query parameters with values `all`/`none` and status "Proposed" (not
  "Supported", unlike the adjacent `xforms_by_name__full` etc. rows).
  `v0_3.CommCareCaseResource` declares `properties = fields.DictField()` and
  `indices = fields.DictField()` (`corehq/apps/api/resources/v0_3.py:33,38`)
  with no `UseIfRequested` wrapper and no code anywhere that reads a
  `properties` or `indices` GET parameter -- contrast the four `__full` fields
  on `v0_4.CommCareCaseResource` (lines 187-209), which really are wrapped in
  `UseIfRequested` and really do gate on a query parameter
  (`corehq/apps/api/fields.py:35-48`). Both fields are dehydrated on every
  request regardless of what (if anything) is passed. The spec does not declare
  `properties`/`indices` as query parameters on either operation; `Case`'s
  `properties`/`indices` properties are documented as always present.
- **The four `__full` flags (`xforms_by_name__full`, `xforms_by_xmlns__full`,
  `child_cases__full`, `parent_cases__full`) work identically on the list
  endpoint, though the docs only mention them under "Case Data Details."**
  `cases-v1.rst`'s list-endpoint Input Parameters table (`cases-v1.rst:29-103`)
  does not mention any of the four; they appear only in the detail endpoint's
  table (`cases-v1.rst:254-273`). But the fields are declared directly on
  `v0_4.CommCareCaseResource` (`corehq/apps/api/resources/v0_4.py:187-209`), and
  `DomainSpecificResourceMixin .get_list`
  (`corehq/apps/api/resources/__init__.py:258-285`) calls `full_dehydrate` on
  every object in a list result exactly as `get_detail` does for a single object
  -- there is no code path that treats list-context dehydration differently from
  detail-context dehydration. A request to the list endpoint with, say,
  `child_cases__full=true` includes `child_cases` on every returned case,
  identically to the detail endpoint. The spec declares all four parameters on
  both `listCases` and `getCase`.
- **The list endpoint's `type` and `name` query parameters are not the parameter
  names the code's non-generic filter path expects, but they work anyway through
  a different path.** `case_param_consumers` (`corehq/apps/api/es.py:356-367`)
  declares `TermParam('case_type', 'type', analyzed=True)` and
  `TermParam('case_name', 'name', analyzed=True)` -- meaning the _specific_
  consumers only pop `case_type`/`case_name` from the query string, not the
  documented `type`/`name` (`cases-v1.rst:44-47,80-83`). However,
  `es_query_from_get_ params`'s fallback loop (`corehq/apps/api/es.py:441-445`)
  filters any unconsumed query parameter as a lowercased term match against the
  Elasticsearch field of the same name -- and the underlying field for case
  type/name is itself named `type`/`name` (the second argument to each
  `TermParam` above). So passing the documented `type=...` or `name=...`
  produces the same filter, by a different code path, as the undocumented
  `case_type=.../case_name=...`. Not a behavioral discrepancy, but worth
  recording since it means two different parameter names filter the same field
  with no code path officially "owning" `type`/`name`. The spec documents `type`
  and `name` as the code actually behaves (functioning, via the fallback path);
  it does not document the undocumented `case_type`/`case_name` alternate names.
- **The list endpoint's Input Parameters table lists `order_by`'s _values_
  (`indexed_on`, `server_date_modified`) as if they were separate query
  parameters.** `cases-v1.rst:96-103` has two rows named `indexed_on` and
  `server_date_modified`, each with an example of `order_by=indexed_on`/
  `order_by=server_date_modified` -- the same pattern the plan's brief warned
  about from the forms API. `order_by` is handled by
  `SimpleSortableResourceMixin.apply_sorting`
  (`corehq/apps/api/resources/__init__.py:224-253`), which accepts any field in
  `self._meta.ordering`; `v0_4.CommCareCaseResource.Meta.ordering`
  (`corehq/apps/api/resources/v0_4.py:230`) is
  `['server_date_modified', 'date_modified', 'indexed_on']` -- three values, not
  two, and each may be prefixed with `-` for descending order (lines 234-239).
  `date_modified` is a valid `order_by` value in code but is absent from the
  docs' two rows entirely. The spec declares a single `order_by` query parameter
  (not two fake ones) describing all three valid values and the `-` prefix.
- **`getCase`'s 404 has an empty body, like `getGroup`'s.**
  `v0_4. CommCareCaseResource.obj_get`
  (`corehq/apps/api/resources/v0_4.py: 220-225`) fetches the case via
  `ESView.get_document` (`corehq/apps/api/es.py:43-52`), which raises Django's
  `ObjectDoesNotExist` on a lookup miss or a domain mismatch. Tastypie's
  `get_detail` (`tastypie/resources.py:1362-1383`) catches `ObjectDoesNotExist`
  directly and returns a bare `http.HttpNotFound()` with no body, never reaching
  the serializer. The spec's `getCase` `404` documents an empty body rather than
  pointing at the shared `NotFound` ref, matching the note already on that ref
  about verifying per-resource.
- **The sample JSON output's `date_modified`/`server_date_modified`/
  `server_date_opened` values end in `Z`, but the code that actually produces
  those fields cannot emit a `Z` or any offset.** `cases-v1.rst: 184,197-198`
  shows `"2012-03-13T18:21:52Z"` / `"2012-04-05T23:56:41Z"` (twice).
  `settings.USE_TZ = False` (`settings.py:57`), so
  `modified_on`/`server_modified_on`/ `server_opened_on` (Django
  `DateTimeField`s, `corehq/form_processor/models/cases.py:318-327`) hold naive
  datetimes. `CommCareCase.to_json()`
  (`corehq/form_processor/models/cases.py: 426-434`) serializes them via
  `CommCareCaseSerializer` (`corehq/form_processor/serializers.py:172-180`, a
  plain DRF `ModelSerializer` with no override for these fields), whose default
  `DateTimeField.to_representation` only appends a `Z`/offset when the value is
  timezone-aware (DRF's `enforce_timezone`, which is a no-op here since `USE_TZ`
  is off and the value is already naive). The resulting string has no `Z` and no
  offset -- confirmed indirectly (no test asserts the literal string), but the
  naive-datetime chain from the DB field through DRF's own documented default
  behavior leaves no path to a `Z` for these three fields. Contrast `indexed_on`
  (`inserted_at`), which genuinely does always end in `Z`:
  `ElasticCase._from_dict` (`corehq/apps/es/cases.py:84`) sets it via
  `json_format_datetime(datetime.utcnow())`
  (`corehq/ex-submodules/dimagi/utils/parsing.py:48-60`), which always strftimes
  with a literal `%Z` suffix in the format string regardless of the input's
  actual tzinfo. The spec's `Case` schema types
  `date_modified`/`date_closed`/`server_date_modified`/ `server_date_opened` as
  naive strings (no `format: date-time`, a `pattern` instead) and keeps
  `format: date-time` only on `indexed_on`, whose example now reflects the real
  always-`Z` shape (`"2012-04-05T23:56:41.000000Z"`). This is a genuine trap for
  an integrator who copies the rst sample literally and expects every date field
  to carry the same shape.
- **`listCases` can return the shared `{"error": ...}` `400` shape from several
  real code paths, undocumented in the reST page.**
  `v0_3. CommCareCaseResource.obj_get_list`
  (`corehq/apps/api/resources/v0_3.py: 59-63`) catches `Http400` (raised for a
  malformed `_search` payload or an unparsable date in a `*_start`/`*_end`
  parameter, via `DateRangeParams.consume_params` -> `validate_date`,
  `corehq/apps/api/es.py:277-308`) and re-raises tastypie's `BadRequest`; an
  invalid `order_by` field raises `InvalidSortError`
  (`SimpleSortableResourceMixin.apply_sorting`,
  `corehq/apps/api/resources/__init__.py:242-246`), itself a `BadRequest`
  subclass (`tastypie/exceptions.py:94`). Tastypie's `wrap_view`
  (`tastypie/resources.py:244-246`) converts any `BadRequest` to the standard
  `{"error": ...}` 400 shape -- the same shape the shared `BadRequest` response
  already documents, so no resource-specific schema is needed. The spec's
  `listCases` declares a `400` using the shared `BadRequest` ref; `getCase` has
  no such code path and declares no `400`.
- **Every entry in `indices` has a third key, `relationship`, that
  `cases-v1.rst` never mentions.** `cases-v1.rst:381-387`'s sample XML shows
  each index entry with only `<case_type>`/`<case_id>`, and the Output Values
  tables (both the list endpoint's and the detail endpoint's) never list a
  `relationship`/similar field at all. `get_index_map`
  (`corehq/form_processor/models/cases.py:839-846`) unconditionally builds every
  entry as
  `{"case_type": ..., "case_id": ..., "relationship": index.relationship}` --
  there is no branch that omits it. `relationship` is drawn from
  `CommCareCaseIndex.relationship_id`, a `PositiveSmallIntegerField` with
  exactly two `choices` (`corehq/form_processor/models/cases.py:1090-1097`),
  mapped to the string constants
  `CASE_INDEX_CHILD = 'child'`/`CASE_INDEX_EXTENSION = 'extension'`
  (`corehq/ex-submodules/casexml/apps/case/const.py:50-51`) -- so it is
  genuinely constrained to two values, not free text. The spec's `Case` schema's
  `indices` sub-object now includes `relationship` as an
  `enum: [child, extension]`.

## case/v2 (`cases-v2.rst`)

Unlike every other resource cross-checked so far, case/v2 is not a tastypie
resource. It is two plain Django views, `case_api` and `case_api_bulk_fetch`
(`corehq/apps/hqcase/views.py:87-127`), so "allowed methods" means "branches of
the view's own `if` chain", and anything that falls through returns a 405
`{"error": "Request method not allowed"}` (`views.py:110`).

- **The create/update response field is `form_id`, not `xform_id`.**
  `cases-v2.rst:552-557`, `:583-588` and `:604-609` all name the returned field
  `xform_id`, in three separate tables. Both response branches of
  `_handle_case_update` (`corehq/apps/hqcase/views.py:281-289`) build
  `{'form_id': xform.form_id, ...}`; there is no `xform_id` key anywhere in the
  view. `corehq/apps/hqcase/tests/test_case_update_api.py:112` asserts the
  response keys are exactly `{'case', 'form_id'}`, and `:899-900` re-asserts
  `'form_id' in res`. An integrator following the reST tables would read
  `xform_id` and get `None`. The spec's `CaseV2WriteResponse` and
  `CaseV2BulkWriteResponse` use `form_id`.
- **Bulk upsert requires `create` to be present and set to `null`; the docs say
  to omit it.** `cases-v2.rst:611-619` says "the 'create' field may be omitted,
  and the API will upsert the case based on the value of 'external_id'".
  `_get_bulk_updates` (`corehq/apps/hqcase/api/updates.py:245-253`) does the
  opposite: `if 'create' not in data: raise UserError("A 'create' flag is
  required for each update.")` comes first, and only then does
  `create_flag = data.pop('create')` / `if create_flag is None:` select the
  upsert path. Omitting the key fails the whole request with a 400; the upsert
  is reached by sending `"create": null`. The spec's `CaseV2BulkChange` marks
  `create` required and documents the three-way `true`/`false`/`null` meaning.
- **The over-limit error is not "Payload too large".** `cases-v2.rst:639-643`
  says "If more than 100 cases are submitted, the server will return a 400
  'Payload too large' response". The real message is
  `f"You cannot submit more than {CASEBLOCK_CHUNKSIZE} updates in a single
  request"` (`corehq/apps/hqcase/api/updates.py:240-241`, with
  `CASEBLOCK_CHUNKSIZE = 100` at `corehq/apps/hqcase/utils.py:28`), delivered
  in the standard `{"error": ...}` body. The 400 status and the 100-case limit
  are both correct; only the message text is wrong. A client matching on the
  string will not match.
- **A non-unique `external_id` is a 400, not a silently-picked case.**
  `cases-v2.rst:395-398` warns: "If the case is identified by its external ID,
  and that ID is not unique, only one case will be returned." Both by-external-id
  operations go through `_get_by_external_id`
  (`corehq/apps/hqcase/views.py:188-200`), which calls
  `get_case_by_external_id(..., raise_multiple=True)`
  (`corehq/form_processor/models/cases.py:102-125`) and converts the resulting
  `MultipleObjectsReturned` into `UserError("Multiple cases found with
  external_id '<id>': <case_ids>")` -> a 400.
  `corehq/apps/hqcase/tests/test_case_update_api.py:851-888` asserts exactly
  this. The warning describes behaviour the code no longer has. Note the
  *bulk-fetch* endpoint is different again: it resolves external ids through
  Elasticsearch (`_get_cases_by_external_id`,
  `corehq/apps/hqcase/api/get_bulk.py:61-70`) with no uniqueness check, so
  there the reST warning is accurate.
- **`PUT /a/<domain>/api/case/v2/` with a single object is an update, not an
  upsert.** `cases-v2.rst:38` lists it as "Upsert case by external ID". With an
  object body the view routes to `_handle_case_put_post(is_creation=False)`
  (`corehq/apps/hqcase/views.py:108-109`) and thence to `JsonCaseUpdate`, whose
  `get_case_id` resolves `external_id` via
  `CaseIDLookerUpper.get_by_external_id`
  (`corehq/apps/hqcase/api/updates.py:157-163,287-291`) and raises
  `UserError("Could not find a case with external_id '<id>'")` when there is no
  match -- a 400, with no case created.
  `corehq/apps/hqcase/tests/test_case_update_api.py:541-551` asserts that 400
  explicitly. Upsert on this path exists only per-entry in an *array* body, via
  `create: null`. The spec's `updateCasesV2` says so in its description.
- **`PUT /a/<domain>/api/case/v2/<case_id>` with an array body returns a 500.**
  Undocumented in the reST page, which only ever shows an object body for the
  detail PUT. `_handle_case_put_post`
  (`corehq/apps/hqcase/views.py:257-258`) runs
  `if not is_creation and case_id and 'case_id' not in data: data['case_id'] =
  case_id` before `handle_case_update` gets a chance to notice the body is a
  list. `'case_id' not in data` is true for a list of dicts, so the next line
  performs `list['case_id'] = ...` and raises `TypeError: list indices must be
  integers or slices, not str`. The view only catches `UserError`
  (`views.py:111-112`), so this surfaces as an unhandled 500. Contrast
  `_handle_ext_put` (`views.py:229-230`), which rejects an array body cleanly
  with a 400. The spec types this operation's request body as a single object
  only and notes the 500.
- **`POST /a/<domain>/api/case/v2/ext/<external_id>/` silently creates an
  unrelated new case.** Neither `cases-v2.rst`'s endpoint table (`:26-39`) nor
  its usage section mentions POST on the by-external-id path, but Django routes
  it (`corehq/apps/api/urls.py:153` maps every method on that path to
  `case_api`). Inside the view the branches are ordered so that
  `request.method == 'POST' and not case_id` (`views.py:104`) matches first --
  `case_id` is empty on this URL, and the `external_id` kwarg is never
  consulted -- so the request is handled as a plain creation and the external id
  in the URL is discarded. A caller who reasonably expects POST-to-ext to behave
  like PUT-to-ext gets a duplicate case with no external id instead. The spec
  deliberately does **not** publish this as an operation; there is an inline
  comment in `paths/case-v2.yaml` saying why, so a later pass does not "fix" it
  back in.
- **`case_api_bulk_fetch` never checks the request method.**
  `corehq/apps/hqcase/views.py:123-127` calls `_handle_bulk_fetch(request)`
  unconditionally. `@allow_cors(['OPTIONS', 'GET', 'POST'])` (`:117`) only sets
  CORS headers; it does not gate dispatch. The consequences: a `GET
  /a/<domain>/api/case/v2/bulk-fetch/` has no body, so it always fails with a
  400 `"Payload must be valid JSON"` even though CORS advertises GET as allowed;
  and a `PUT` to that path, which CORS does not advertise, works exactly like
  `POST`. The spec documents only `POST`, with an inline comment recording this.
- **Three list-endpoint filters are missing from the reST filter table.** The
  table at `cases-v2.rst:245-292` omits `query`, `include_deprecated` and
  `cursor`. `query` takes a case-search XPath expression and is applied as an
  extra filter (`_get_filter`/`_get_query_filter`,
  `corehq/apps/hqcase/api/get_list.py:154-172`); `include_deprecated` is in
  `SIMPLE_FILTERS` (`:62-69`) and, when absent or false, silently *excludes*
  cases whose type is deprecated in the data dictionary
  (`_include_deprecated_filter`, `:51-55`) -- so the default result set is
  already narrower than the documented filters imply; `cursor` is consumed at
  the top of `get_list` (`:85-91`) and is how the documented `next` link works.
  The reST page also does not say that an unrecognised parameter is rejected:
  `_get_filter` (`:164-165`) raises `UserError("'<key>' is not a valid
  parameter.")`, a 400 -- a real behaviour change from case/v1, which turns
  unknown parameters into raw Elasticsearch term filters. All four points are
  in the spec's `listCasesV2`.
- **`indices` is always present on a read, not "not included by default".**
  `cases-v2.rst:122-124` annotates the `indices` row of the read-serialization
  table with "(not included by default)". Both serializers build the key
  unconditionally -- `serialize_case`
  (`corehq/apps/hqcase/api/core.py:24-31`) and `serialize_es_case`
  (`:59-66`) each end with an `"indices": {...}` dict comprehension, which
  yields `{}` for a case with no indices rather than omitting the key. The
  sample payload at `:65-71` shows `indices` present, contradicting the table on
  the same page. The spec documents it as always present.
- **`temporary_id` is a creation-only field, not a "bulk create/update" field.**
  `cases-v2.rst:188-192` describes the top-level `temporary_id` as "Bulk
  create/update only". It is declared on `JsonCaseCreation`
  (`corehq/apps/hqcase/api/updates.py:128-129`) and on neither
  `JsonCaseUpdate` nor `JsonCaseUpsert`, and `BaseJsonCaseChange.wrap`
  (`:87-94`) rejects any key that is not a declared property. So it is rejected
  with `"'temporary_id' is not a valid field."` on every update, bulk or not,
  and it is *accepted* (though it can do nothing useful) on a non-bulk single
  create. The nested `indices.<name>.temporary_id`, described the same way at
  `:216-220`, is different: it lives on `JsonIndex` (`:46`) and is accepted on
  every payload shape, bulk or not. The spec places `temporary_id` on
  `CaseV2Create` and `CaseV2BulkChange` only, and the index-level
  `temporary_id` on the shared `CaseV2WriteIndexEntry`.
- **Creates return 200, not 201.** Not stated either way in the reST page. Both
  write branches return a plain `JsonResponse` (`views.py:281-289`), whose
  default status is 200, including for a creation. This differs from the
  group resource, whose create is a 201. Worth knowing for a client that
  branches on the status code.
- **The rate-limit response has an empty body, unlike the rest of the API.**
  Not covered by the reST page. This resource is throttled by `api_throttle`
  (`corehq/apps/api/decorators.py:51-61`), which returns
  `HttpResponse(status=429, headers={'Retry-After': ...})` -- no content and no
  serializer. The spec's shared `TooManyRequests` response documents an
  `{"error": ...}` JSON body, so every case/v2 operation declares its own 429
  with a `Retry-After` header and no `content`, rather than pointing at the
  shared ref.
