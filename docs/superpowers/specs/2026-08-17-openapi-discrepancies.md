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
- **Correction (fix round 3): an earlier version of this entry claimed
  `date_modified`/`server_date_modified`/`server_date_opened` cannot emit a
  `Z`/offset, contradicting the rst's own `Z`-suffixed JSON sample. That claim
  was wrong and is retracted -- these fields, and `date_closed`, do genuinely
  emit a `Z`, so the sample was not a discrepancy after all.** The earlier
  reasoning stopped at `settings.USE_TZ = False` (`settings.py:57`) plus DRF's
  default ISO-8601 `DateTimeField` behavior (which only appends `Z` for a
  timezone-_aware_ value) and concluded these naive fields must be Z-less. It
  missed that this project overrides DRF's global output format:
  `REST_FRAMEWORK = {'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ'}`
  (`settings.py:2083-2085`). DRF's `DateTimeField.to_representation`
  (`rest_framework/fields.py:1198-1214`) computes
  `output_format = getattr(self, 'format', api_settings.DATETIME_FORMAT)`; since
  none of `CommCareCaseSerializer`'s auto-generated fields
  (`corehq/form_processor/serializers.py:172-180`) override `format`,
  `output_format` resolves to that project-wide strftime pattern. Because the
  pattern is not `'iso-8601'`, `to_representation` takes the
  `return value.strftime(output_format)` branch, not the ISO-8601 branch that
  gates the `Z` on timezone-awareness -- `strftime` appends the literal `Z`
  character unconditionally, regardless of whether `value` is naive. So
  `modified_on`/`closed_on`/`server_modified_on`/ `server_opened_on`, serialized
  through `CommCareCase.to_json()`
  (`corehq/form_processor/models/cases.py:426-434`) at case-indexing time, all
  come out `Z`-suffixed with six-digit microseconds -- the same shape as
  `indexed_on`. The only real (minor) gap: the rst sample omits microseconds
  (`"2012-03-13T18:21:52Z"`) while the code always includes six digits
  (`"2012-03-13T18:21:52.000000Z"`) -- a cosmetic simplification in the docs,
  not a shape error. The spec's `Case` schema now types all five date fields
  (`date_modified`, `date_closed`, `server_date_modified`, `server_date_opened`,
  `indexed_on`) as `format: date-time` with `Z`-suffixed, microsecond-precision
  examples.
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
  opposite:
  `if 'create' not in data: raise UserError("A 'create' flag is required for each update.")`
  comes first, and only then does `create_flag = data.pop('create')` /
  `if create_flag is None:` select the upsert path. Omitting the key fails the
  whole request with a 400; the upsert is reached by sending `"create": null`.
  The spec's `CaseV2BulkChange` marks `create` required and documents the
  three-way `true`/`false`/`null` meaning.
- **The over-limit error is not "Payload too large".** `cases-v2.rst:639-643`
  says "If more than 100 cases are submitted, the server will return a 400
  'Payload too large' response". The real message is
  `f"You cannot submit more than {CASEBLOCK_CHUNKSIZE} updates in a single request"`
  (`corehq/apps/hqcase/api/updates.py:240-241`, with `CASEBLOCK_CHUNKSIZE = 100`
  at `corehq/apps/hqcase/utils.py:28`), delivered in the standard
  `{"error": ...}` body. The 400 status and the 100-case limit are both correct;
  only the message text is wrong. A client matching on the string will not
  match.
- **A non-unique `external_id` is a 400, not a silently-picked case.**
  `cases-v2.rst:395-398` warns: "If the case is identified by its external ID,
  and that ID is not unique, only one case will be returned." Both
  by-external-id operations go through `_get_by_external_id`
  (`corehq/apps/hqcase/views.py:188-200`), which calls
  `get_case_by_external_id(..., raise_multiple=True)`
  (`corehq/form_processor/models/cases.py:102-125`) and converts the resulting
  `MultipleObjectsReturned` into
  `UserError("Multiple cases found with external_id '<id>': <case_ids>")` ->
  a 400. `corehq/apps/hqcase/tests/test_case_update_api.py:851-888` asserts
  exactly this. The warning describes behaviour the code no longer has. Note the
  _bulk-fetch_ endpoint is different again: it resolves external ids through
  Elasticsearch (`_get_cases_by_external_id`,
  `corehq/apps/hqcase/api/get_bulk.py:61-70`) with no uniqueness check, so there
  the reST warning is accurate.
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
  explicitly. Upsert on this path exists only per-entry in an _array_ body, via
  `create: null`. The spec's `updateCasesV2` says so in its description.
- **`PUT /a/<domain>/api/case/v2/<case_id>` with an array body returns a 500.**
  Undocumented in the reST page, which only ever shows an object body for the
  detail PUT. `_handle_case_put_post` (`corehq/apps/hqcase/views.py:257-258`)
  runs
  `if not is_creation and case_id and 'case_id' not in data: data['case_id'] = case_id`
  before `handle_case_update` gets a chance to notice the body is a list.
  `'case_id' not in data` is true for a list of dicts, so the next line performs
  `list['case_id'] = ...` and raises
  `TypeError: list indices must be integers or slices, not str`. The view only
  catches `UserError` (`views.py:111-112`), so this surfaces as an
  unhandled 500. Contrast `_handle_ext_put` (`views.py:229-230`), which rejects
  an array body cleanly with a 400. The spec types this operation's request body
  as a single object only and notes the 500.
- **`POST /a/<domain>/api/case/v2/ext/<external_id>/` silently creates an
  unrelated new case.** Neither `cases-v2.rst`'s endpoint table (`:26-39`) nor
  its usage section mentions POST on the by-external-id path, but Django routes
  it (`corehq/apps/api/urls.py:153` maps every method on that path to
  `case_api`). Inside the view the branches are ordered so that
  `request.method == 'POST' and not case_id` (`views.py:104`) matches first --
  `case_id` is empty on this URL, and the `external_id` kwarg is never consulted
  -- so the request is handled as a plain creation and the external id in the
  URL is discarded. A caller who reasonably expects POST-to-ext to behave like
  PUT-to-ext gets a duplicate case with no external id instead. The spec
  deliberately does **not** publish this as an operation; there is an inline
  comment in `paths/case-v2.yaml` saying why, so a later pass does not "fix" it
  back in.
- **`case_api_bulk_fetch` never checks the request method.**
  `corehq/apps/hqcase/views.py:123-127` calls `_handle_bulk_fetch(request)`
  unconditionally. `@allow_cors(['OPTIONS', 'GET', 'POST'])` (`:117`) only sets
  CORS headers; it does not gate dispatch. The consequences: a
  `GET /a/<domain>/api/case/v2/bulk-fetch/` has no body, so it always fails with
  a 400 `"Payload must be valid JSON"` even though CORS advertises GET as
  allowed; and a `PUT` to that path, which CORS does not advertise, works
  exactly like `POST`. The spec documents only `POST`, with an inline comment
  recording this.
- **Three list-endpoint filters are missing from the reST filter table.** The
  table at `cases-v2.rst:245-292` omits `query`, `include_deprecated` and
  `cursor`. `query` takes a case-search XPath expression and is applied as an
  extra filter (`_get_filter`/`_get_query_filter`,
  `corehq/apps/hqcase/api/get_list.py:154-172`); `include_deprecated` is in
  `SIMPLE_FILTERS` (`:62-69`) and, when absent or false, silently _excludes_
  cases whose type is deprecated in the data dictionary
  (`_include_deprecated_filter`, `:51-55`) -- so the default result set is
  already narrower than the documented filters imply; `cursor` is consumed at
  the top of `get_list` (`:85-91`) and is how the documented `next` link works.
  The reST page also does not say that an unrecognised parameter is rejected:
  `_get_filter` (`:164-165`) raises
  `UserError("'<key>' is not a valid parameter.")`, a 400 -- a real behaviour
  change from case/v1, which turns unknown parameters into raw Elasticsearch
  term filters. All four points are in the spec's `listCasesV2`.
- **`indices` is always present on a read, not "not included by default".**
  `cases-v2.rst:122-124` annotates the `indices` row of the read-serialization
  table with "(not included by default)". Both serializers build the key
  unconditionally -- `serialize_case` (`corehq/apps/hqcase/api/core.py:24-31`)
  and `serialize_es_case` (`:59-66`) each end with an `"indices": {...}` dict
  comprehension, which yields `{}` for a case with no indices rather than
  omitting the key. The sample payload at `:65-71` shows `indices` present,
  contradicting the table on the same page. The spec documents it as always
  present.
- **`temporary_id` is a creation-only field, not a "bulk create/update" field.**
  `cases-v2.rst:188-192` describes the top-level `temporary_id` as "Bulk
  create/update only". It is declared on `JsonCaseCreation`
  (`corehq/apps/hqcase/api/updates.py:128-129`) and on neither `JsonCaseUpdate`
  nor `JsonCaseUpsert`, and `BaseJsonCaseChange.wrap` (`:87-94`) rejects any key
  that is not a declared property. So it is rejected with
  `"'temporary_id' is not a valid field."` on every update, bulk or not, and it
  is _accepted_ (though it can do nothing useful) on a non-bulk single create.
  The nested `indices.<name>.temporary_id`, described the same way at
  `:216-220`, is different: it lives on `JsonIndex` (`:46`) and is accepted on
  every payload shape, bulk or not. The spec places `temporary_id` on
  `CaseV2Create` and `CaseV2BulkChange` only, and the index-level `temporary_id`
  on the shared `CaseV2WriteIndexEntry`.
- **Creates return 200, not 201.** Not stated either way in the reST page. Both
  write branches return a plain `JsonResponse` (`views.py:281-289`), whose
  default status is 200, including for a creation. This differs from the group
  resource, whose create is a 201. Worth knowing for a client that branches on
  the status code.
- **The rate-limit response has an empty body, unlike the rest of the API.** Not
  covered by the reST page. This resource is throttled by `api_throttle`
  (`corehq/apps/api/decorators.py:51-61`), which returns
  `HttpResponse(status=429, headers={'Retry-After': ...})` -- no content and no
  serializer. The spec's shared `TooManyRequests` response documents an
  `{"error": ...}` JSON body, so every case/v2 operation declares its own 429
  with a `Retry-After` header and no `content`, rather than pointing at the
  shared ref.

## form/v1 and submission (`list-forms.rst`, `form-data.rst`, `form-submission.rst`)

- **`order_by` values are documented as separate parameters.** The table at
  `list-forms.rst:65-73` lists `indexed_on`, `server_modified_on`, and
  `received_on` as if they were parameter names in their own right ("Name"
  column), but their "Example" column shows `order_by=indexed_on`, etc. -- they
  are **values** of the single `order_by` parameter, not parameters themselves.
  The three values do match `v0_4.XFormInstanceResource.Meta.ordering`
  (`corehq/apps/api/resources/v0_4.py:170`) exactly (as a set; the doc lists
  them in a different order than the code), so there is no discrepancy in
  _which_ fields are sortable, only in how the table presents them. The spec
  models `order_by` as a single enum parameter on `listForms`.
- **`include_archived` is checked for presence, not for the value `"true"`.**
  `list-forms.rst:59-61` says "When set to 'true' archived forms will be
  included". The actual check,
  `if query_params.pop('include_archived', None) is not None:`
  (`corehq/apps/api/es.py:411`), is true for _any_ supplied value --
  `include_archived=false`, `include_archived=0`, or `include_archived=anything`
  all include archived forms; only omitting the parameter entirely excludes
  them.
- **`appVersion` and `app_id` are matched case-insensitively; `xmlns` and
  `case_id` are not.** Neither `appVersion` nor `app_id` has a dedicated entry
  in `xform_param_consumers` (`corehq/apps/api/es.py:346-354`), so both fall
  through to the "unconsumed filters" branch (`corehq/apps/api/es.py:440-445`),
  which unconditionally lowercases the value before filtering. `xmlns`
  (`TermParam('xmlns', 'xmlns.exact')`) and `case_id`
  (`TermParam('case_id', '__retrieved_case_ids')`) are both `TermParam`
  instances with the default `analyzed=False`, so their values are matched
  as-is. None of this is mentioned in `list-forms.rst`.
- **The attachment `url` field in the sample output is undocumented.** The
  sample at `list-forms.rst:97-105` shows an `attachments` entry with only
  `content_type` and `length`. In practice each attachment also carries a `url`
  key pointing at the `getFormAttachment` operation (`dehydrate_attachments`,
  `corehq/apps/api/resources/v0_4.py:113-118`, using
  `absolute_reverse('api_form_attachment', ...)`).
- **The `cases`/`cases__full` field is entirely undocumented.**
  `v0_4.XFormInstanceResource.cases`
  (`corehq/apps/api/resources/v0_4.py:96-101`) is a real, working
  `UseIfRequested` field returning the cases a form updated, gated by
  `cases__full=true`, exactly like the analogous `xforms_by_name__full` etc.
  fields on the case resource. Neither `list-forms.rst` nor `form-data.rst`
  mentions it.
- **Two additional working date-range filters exist in code but are
  undocumented, matching a precedent already accepted for cases/v1.**
  `xform_param_consumers` (`corehq/apps/api/es.py:346-354`) also registers
  `DateRangeParams('server_modified_on')` -- i.e. `server_modified_on_start` /
  `server_modified_on_end` -- alongside the aliased
  `DateRangeParams('server_date_modified', 'server_modified_on')` that
  `list-forms.rst` likewise never documents. (The analogous case is
  `case_param_consumers`, `corehq/apps/api/es.py:356-367`, where `cases-v1.rst`
  documents only `server_date_modified_start`/`_end` and `case-v1.yaml` does not
  model the raw `server_modified_on_start`/`_end` duplicate either.) Left
  undocumented in the spec for consistency with that precedent; noted here for
  visibility.
- **A third, distinct 404 shape appears within this same resource group.**
  `getForm`'s 404 (tastypie catching `ObjectDoesNotExist`, bare
  `http.HttpNotFound()`, empty body -- same as `getCase`) is different from
  `getFormAttachment`'s 404: `get_form_attachment_response`
  (`corehq/apps/reports/views.py:1517-1520`) raises a bare Django `Http404` on
  `AttachmentNotFound`, which is handled by Django's own `page_not_found`
  (`handler404 = not_found`, `urls.py:47`) and rendered as an HTML page, not
  JSON. Neither reST page discusses this.
- **`getForm`/`listForms`'s 403 body is empty, not the shared `{"error": ...}`
  shape.** Traced through `RequirePermissionAuthentication.is_authenticated`
  (`corehq/apps/api/resources/auth.py:152-163`) ->
  `LoginAndDomainAuthentication._auth_test`
  (`corehq/apps/api/resources/auth.py:114-135`): a failed permission check
  raises `PermissionDenied` (`require_permission_raw`,
  `corehq/apps/users/decorators.py:34-54`), which `_auth_test` catches directly
  and converts to a bare `HttpResponseForbidden()`. Only an _auth_ failure (not
  a permission failure) passes through `wrap_4xx_errors_for_apis`
  (`corehq/apps/api/resources/auth.py:23-34`) and gets the JSON
  `{"error": "not authorized"}` 401 body the shared `Unauthorized` component
  documents -- that part of the shared ref is correct for these two operations,
  but `Forbidden` is not.
- **`submitForm`/`submitFormForApp`'s 401 and 403 bodies are HTML or
  backend-specific, not the shared JSON shape.** Both are plain Django views
  (`post_api`/`post`, `corehq/apps/receiverwrapper/views.py:278-320`), not
  tastypie resources, so `HqBaseResource`'s JSON error handling never applies.
  `post_api`'s `@require_permission(HqPermissions.edit_data)` /
  `@require_permission(HqPermissions.access_api)` raise `PermissionDenied` on
  failure, rendered by this project's `handler403 = no_permissions`
  (`urls.py:47`) as `HttpResponseForbidden(_no_permissions_message(...))`
  (`corehq/apps/hqwebapp/views.py:362-373`) -- an HTML page. `post`
  (`submitFormForApp`) returns a bare, empty-body `HttpResponseForbidden()` for
  a mobile-access failure (`corehq/apps/receiverwrapper/views.py:88-89`). 401s
  on both come from whichever HTTP auth backend is in play (digest by default),
  not from a JSON envelope.
- **The submission success/error response `Content-Type` header contradicts the
  OpenRosa standard the endpoint claims to implement.**
  `OpenRosaResponse.response`
  (`corehq/ex-submodules/couchforms/openrosa_response.py:58-59`) calls
  `HttpResponse(self.xml(), status=self.status)` without a `content_type`
  argument, and no caller in `submission_post.py` or `receiverwrapper/views.py`
  sets one either. `settings.py` never overrides `DEFAULT_CONTENT_TYPE`, so
  Django's default (`text/html; charset=utf-8`) applies to every OpenRosa
  response body, even though the body is genuinely XML per
  https://bitbucket.org/javarosa/javarosa/wiki/FormSubmissionAPI. This is a real
  bug, not a documentation gap: a client that content-negotiates or branches on
  the response media type will not recognize it as XML. The spec declares the
  response content type as `text/html` (what the code actually sends) and puts
  the "it's really XML" explanation in the schema description, per the project's
  binding rule that the spec records what the code does.
- **`submitFormForApp` has a materially different auth/permission model than
  `submitForm`, undocumented by `form-submission.rst`.** `submitForm`
  (`post_api`) always requires authentication plus the Edit Data and Access APIs
  permissions. `submitFormForApp` (`post`,
  `corehq/apps/receiverwrapper/views.py:297-320`) checks
  `domain_requires_auth(domain)`: if true, it delegates to `secure_post`
  (requiring digest, basic, API-key, or OAuth2 auth, but no explicit permission
  beyond a valid login); if false, the form is processed fully unauthenticated
  (`authenticated=False`, `user_id=None`). Most production domains enable secure
  submissions, so this is rarely reachable in practice, but the code path exists
  and neither reST page mentions it.
- **The outbound OpenRosa version response header is literally named
  `HTTP_X_OPENROSA_VERSION`, not `X-OpenRosa-Version`.** This is a real
  interoperability bug, not a documentation nit: an OpenRosa client looking for
  the standard header name will not find it.
  `OPENROSA_VERSION_HEADER = "HTTP_X_OPENROSA_VERSION"`
  (`corehq/middleware.py:35`) is the WSGI `META` key used to read the _request_
  header, but `OpenRosaMiddleware.process_response`
  (`corehq/middleware.py:55-57`) reuses that same string as the _response_
  header name: `response[OPENROSA_VERSION_HEADER] = OPENROSA_DEFAULT_VERSION`.
  Django's `HttpResponse` sends whatever string is used as the response mapping
  key verbatim, with no `HTTP_`-prefix translation (that convention only applies
  to WSGI's `request.META`), so the actual outbound header on every CommCare HQ
  response -- not just submission responses -- is named
  `HTTP_X_OPENROSA_VERSION`. A second reference confirms the same literal key is
  used on the response side elsewhere: `del response['HTTP_X_OPENROSA_VERSION']`
  (`corehq/middleware.py:258`). The spec's `X-OpenRosa-Version` header parameter
  models the _request_ header apps must send (which is read from
  `request.META['HTTP_X_OPENROSA_VERSION']`, the correct WSGI convention for an
  incoming `X-OpenRosa-Version` header), and its description separately notes
  that the outbound response header name does not match the standard.

## user/v1 and web-user/v1 (`list-mobile-workers.rst`, `mobile-worker.rst`, `list-webusers.rst`, `webuser.rst`)

- **`webuser.rst` documents `.../activate/` and `.../deactivate/` at
  `/api/web-user/v1/{id}/...`, and they are real** -- resolved, not a
  documentation error. `WebUserResource.prepend_urls`
  (`corehq/apps/api/resources/v0_5.py:600-605`) registers exactly those two
  URLs, wrapping `enable_user`/`disable_user` ->
  `_modify_user_status` (`v0_5.py:607-633`), which flips
  `domain_membership.is_active` and returns 202 with an empty `{}` body. The
  spec documents both as real operations (`activateWebUser`,
  `deactivateWebUser`). **The one part of the brief's framing that does not
  hold up: `webuser.rst` never actually documents a `POST
  /api/web-user/v1/` "create web user" endpoint.** Its "Web User Invitation
  Creation" section (which is the only `POST` in the file) is a `POST
  /api/invitation/v1/`, a different resource entirely
  (`v1_0.InvitationResource`) that creates an `Invitation`, not a `WebUser` --
  the `WebUser` itself is only created once the invitation is accepted.
  `v0_5.WebUserResource.Meta` really does decline `post` everywhere
  (`detail_allowed_methods = ['get', 'patch']`, inherited
  `list_allowed_methods = ['get']`), so there is no discrepancy to record
  there; the reST docs simply never claimed it.
- **Mobile workers have the identical activate/deactivate machinery, entirely
  undocumented in either mobile-worker reST page.**
  `CommCareUserResource.prepend_urls` (`v0_5.py:412-418`) registers
  `.../activate/`, `.../deactivate/`, and `.../email_password_reset/`
  (the last of which *is* documented, at `mobile-worker.rst:297-313`); the
  first two are not mentioned in `mobile-worker.rst` at all, despite being
  real, tested (`corehq/apps/api/tests/test_user_resources.py:582-628`)
  endpoints with a location-based permission check
  (`verify_modify_user_conditions`) that the web user equivalent lacks. The
  spec documents both as real operations (`activateMobileWorker`,
  `deactivateMobileWorker`).
- **`createMobileWorker` silently discards field-update errors that
  `updateMobileWorker` rejects with a 400.** `obj_create`
  (`corehq/apps/api/resources/v0_5.py:321`) calls `self._update(bundle)` and
  ignores its return value; `obj_update` (`v0_5.py:356-359`) calls the exact
  same helper and raises `BadRequest` if the returned `errors` list is
  non-empty. `_update` returns a list of per-field validation failures
  (`v0_5.py:396-410`, via `CommcareUserUpdates.update`, which raises
  `UpdateUserException` per bad field and is caught and collected). The
  practical effect: submitting an invalid `primary_location`, `locations`
  entry, or other updater-rejected field on `POST` creates the user anyway,
  with that field silently unset, instead of failing with a 400 the way the
  same payload would on `PUT`. Neither `mobile-worker.rst` nor
  `list-mobile-workers.rst` mentions this asymmetry.
- **`getMobileWorker`, `getWebUser`, and `updateWebUser` return a 400, not a
  404, for a missing or wrong-domain `user_id`.** (Corrected in fix round 1:
  an earlier version of this entry claimed all three return an uncaught 500.
  That was wrong about the response status/shape, though right that the code
  has no working 404 for any of them.) `UserResource.obj_get`
  (`corehq/apps/api/resources/v0_1.py:36-43`) calls
  `self.Meta.object_class.get_by_user_id(pk, domain)`
  (`corehq/apps/users/models.py:1529-1544`), which returns `None` -- it never
  raises, on a miss or a domain mismatch (the `except KeyError` in `obj_get`
  is dead code; `get_by_user_id` cannot raise `KeyError`). Tastypie's
  `get_detail`/`patch_detail` (`tastypie/resources.py:1362-1383,1680-1688`)
  only convert `ObjectDoesNotExist`/`MultipleObjectsReturned` to a 404, so the
  bare `None` reaches `full_dehydrate`
  (`tastypie/resources.py:877-902`). There, `ApiField.dehydrate`
  (`tastypie/fields.py:116-136`) does `getattr(None, attr, None)`; since
  `id`/`username`/`email` are declared without `null=True` and without a
  default (`v0_1.py:27-32`), it raises `tastypie.fields.ApiFieldError`
  (`"The object 'None' has an empty attribute 'get_id' and doesn't allow a
  default or null value."`). `wrap_view`'s `except (BadRequest,
  fields.ApiFieldError)` (`tastypie/resources.py:244-246`) catches this
  **explicitly, before** the generic `except Exception` -> `_handle_500`
  path, and converts it to a 400 with the shared `{"error": "..."}` shape --
  the same shape the shared `Error` schema already documents. `updateWebUser`
  (`PATCH`) hits the identical path, since `patch_detail` calls
  `cached_obj_get` and `full_dehydrate` before `obj_update` ever runs.
  Neither reST page states what happens for a nonexistent id. The spec
  points all three operations' `400` at the shared `Error` schema and omits
  `404`, each with an inline comment tracing this path.
- **`updateMobileWorker` (`PUT`) also has no working 404 -- but unlike the
  three operations above, this one really is an uncaught 500, the analogous
  bug to `replaceGroup`'s in `paths/group.yaml`.** Its crash happens inside
  the resource's own `obj_update` override, before tastypie's
  dehydration/`ApiFieldError` machinery is ever reached, so `wrap_view`'s
  `ApiFieldError`/`BadRequest` catch (see the entry above) does not apply
  here. `obj_update`
  (`corehq/apps/api/resources/v0_5.py:352-353`) fetches with
  `CommCareUser.get(kwargs['pk'])` (couchdbkit's plain `.get()`, raising
  `ResourceNotFound` on a miss) and then asserts
  `bundle.obj.domain == kwargs['domain']` with a bare `assert`. Neither
  exception is tastypie's `NotFound`/`MultipleObjectsReturned` (the only pair
  `put_detail` catches, `tastypie/resources.py:1502`), so both become
  uncaught 500s. The spec omits `404` on `updateMobileWorker`, with an inline
  comment.
- **`deleteMobileWorker`'s 404 does work, and is empty-bodied.** Contrast the
  above: `obj_delete` (`corehq/apps/api/resources/v0_5.py:375-381`) explicitly
  raises tastypie's own `NotFound(...)` when the lookup fails, and
  `delete_detail` (`tastypie/resources.py:1525-1541`) does catch that
  exception type, returning a bare `http.HttpNotFound()`. This is the one
  detail operation across both resources whose 404 is genuine.
  `test_cant_delete_user_in_another_domain`
  (`corehq/apps/api/tests/test_user_resources.py:569-580`) confirms the 404
  status for a cross-domain id.
- **A fourth 404 shape, distinct from all previously catalogued ones:**
  `email_password_reset`, `activate_user`/`deactivate_user`, and
  `enable_user`/`disable_user` all raise a bare, argument-less tastypie
  `NotFound()` (`v0_5.py:435,456,622`) from inside a custom `prepend_urls`
  view. Because these views are reached through `wrap_view` directly, not
  through `dispatch_detail`/`delete_detail`'s own `except NotFound` handling,
  the exception falls to `wrap_view`'s generic `except Exception` ->
  `_handle_500` (`tastypie/resources.py:250-265,291-315`), which does
  recognize `NotFound` and maps it to a 404 status, but always builds the
  body from the canned-error path (`{"error_message": "Sorry, this request
  could not be processed. Please try again later."}` outside `DEBUG`) --
  never the (here, empty) exception text, and never anything
  resource-specific. This is the same underlying mechanism as `deleteGroup`'s
  404 in `paths/group.yaml`, just reached from a different kind of view.
- **`updateWebUser` and `inviteWebUser` share a `400` body shape keyed
  `errors` (plural, a list), found nowhere else in this spec.**
  `WebUserValidationException.__init__`
  (`corehq/apps/api/validation.py:31-33`) always normalizes its message to a
  list; both call sites
  (`WebUserResource.obj_update`, `v0_5.py:563-564`; `InvitationResource
  .obj_create`, `v1_0.py:124-125`) wrap it as
  `ImmediateHttpResponse(JsonResponse({"errors": e.message}, status=400))`,
  bypassing tastypie's usual `BadRequest` -> `{"error": ...}` conversion
  entirely. `inviteWebUser` additionally has a *third* 400 shape for a
  location id that passes `WebUserResourceSpec` validation but does not
  resolve to a real `SQLLocation`: `{"error": "Could not find location ids:
  ..."}` (`v1_0.py:139-141`) -- singular `error`, matching the shared shape,
  from a different code path than either of the other two. Neither reST page
  documents any error-body shape. The spec's `WebUserErrors` schema covers
  the `errors` shape; the shared `Error` schema covers the singular one.
- **`inviteWebUser`'s reST documentation contradicts itself about whether
  `id` is returned, and neither version matches the code.**
  `webuser.rst`'s "Output Parameters" table (lines 68-79) says the response
  contains only `id`. Its own "Sample output (JSON)" three sections later
  (lines 101-120) shows every field *except* `id`. `InvitationResource`
  declares `id = fields.CharField(attribute='uuid', readonly=True,
  unique=True)` (`v1_0.py:77`) and `always_return_data = True`
  (`v1_0.py:91`), so `full_dehydrate` includes `id` alongside every other
  declared field on every response -- neither reST claim is correct. The
  spec's `Invitation` schema documents the real (everything-including-`id`)
  shape.
- **`list-webusers.rst`'s Output Parameters table is missing six of the
  thirteen fields `WebUserResource` actually serializes.**
  `list-webusers.rst:43-80` lists only `id`, `username`, `first_name`,
  `last_name`, `default_phone_number`, `email`, `phone_numbers`, `role`,
  `permissions`, `is_admin`. `v0_5.WebUserResource` additionally declares
  `primary_location_id`, `assigned_location_ids`, `profile`, `user_data`,
  `tableau_role`, and `is_active_in_domain` (`v0_5.py:474-479`) with no
  `use_in` restriction, so all six appear on *every* list and detail
  response, not just detail. (`tableau_groups`, the seventh extra field, is
  the one exception -- see the next entry.) All six do appear, undocumented,
  in `webuser.rst`'s PATCH sample response (lines 210-292), so they are not
  unknown to the docs generally, just missing from the list endpoint's own
  Output Parameters table. The spec's `WebUser` schema includes all six, each
  flagged as undocumented there.
- **`tableau_groups` is real but genuinely list/detail-asymmetric, and
  undocumented on both endpoints' Output Parameters tables.**
  `tableau_groups = fields.ListField(null=True, use_in='detail')`
  (`v0_5.py:481`) is the only field on either user resource with a
  non-default `use_in`; the inline code comment explains why (computing it
  makes one request per user, too slow for a list). It appears on
  `getWebUser` but never on `listWebUsers`. The spec's `WebUser` schema
  documents this list/detail difference explicitly rather than modelling one
  shape for both operations.
- **Both resources emit an `eulas` field that is a Python `repr` string, not
  structured data, undocumented on both list endpoints.**
  `UserResource.eulas = fields.CharField(attribute='eulas', null=True)`
  (`v0_1.py:34`, inherited by both `CommCareUserResource` and
  `WebUserResource`) combined with `tastypie.fields.CharField.convert`
  calling `str()` unconditionally
  (`tastypie/fields.py:211-215`) means the field's value is literally
  `str()` of a list of `LicenseAgreement` objects. `webuser.rst`'s PATCH
  sample response (line 216) shows this exact shape
  (`"eulas": "[LicenseAgreement(date=datetime.datetime(...), ...)]"`), but
  neither `list-mobile-workers.rst` nor `list-webusers.rst` mentions the
  field at all. The spec's `MobileWorker`/`WebUser` schemas document `eulas`
  as a plain string with a description explaining the repr shape.
- **`resource_uri` is a real field on every response from both resources,
  documented incorrectly or not at all.** `include_resource_uri` is never
  set to `False` anywhere in the inheritance chain
  (`CustomResourceMeta`, `corehq/apps/api/resources/meta.py:76-81`), and both
  `CommCareUserResource.get_resource_uri` (`v0_5.py:257-268`) and
  `WebUserResource.get_resource_uri` (`v0_5.py:524-532`) are overridden to
  always compute a real detail URL. `list-mobile-workers.rst`'s Output Values
  table and sample JSON omit the field entirely.
  `list-webusers.rst`'s sample JSON (lines 118, 139) does include it, but
  shows it as an always-empty string (`"resource_uri":""`) -- stale, not the
  real behavior. The spec's `MobileWorker`/`WebUser` schemas document the
  field as a real, always-populated URL.
- **`default_phone_number` is a genuine, separately recognized write field on
  the mobile worker resource, missing from `mobile-worker.rst`'s Input
  Parameters table.** `CommcareUserUpdates.update`
  (`corehq/apps/api/user_updates.py:148`) maps `'default_phone_number'` to
  `_update_default_phone_number` (`user_updates.py:204-214`), which adds the
  number to `phone_numbers` if new and marks it default -- independent of, and
  in addition to, the "first entry of `phone_numbers` becomes default"
  behavior the table does document. The reST page's own sample input (line
  107) includes the field redundantly, without it ever appearing in the
  Input Parameters table above. The spec's `MobileWorkerWrite` schema
  documents it as a real property.
- **`connect_username` is a real, undocumented create-only field, gated by a
  feature toggle.** `obj_create`
  (`corehq/apps/api/resources/v0_5.py:278,280-281,334-338`) reads
  `connect_username` from the request body, rejects it with a 400 unless the
  `COMMCARE_CONNECT` toggle is enabled for the domain, and otherwise links
  the new user to a `ConnectIDUserLink` instead of requiring a password.
  Absent from `mobile-worker.rst`'s Input Parameters table entirely. The
  spec's `MobileWorkerWrite` schema documents it, with the toggle
  requirement noted.
- **No credential is ever returned in any response body.** Checked
  specifically per the task brief's instruction to flag this prominently if
  found: neither `UserResource` (`v0_1.py:25-34`) nor either subclass
  declares a `password` field at all, so tastypie's `full_dehydrate` -- which
  only serializes explicitly declared `fields.*` attributes -- can never
  include one, regardless of what was submitted on create/update.
  `CommCareUserResource.obj_create` additionally pops `password` from
  `bundle.data` immediately after use (`v0_5.py:317-318`), before any
  dehydration happens. **Nothing to flag; this is a negative finding,
  included for completeness.**
- **`type: "user"` (shown in `list-mobile-workers.rst`'s sample JSON, lines
  119 and 144) is never actually serialized.** `UserResource.type = "user"`
  (`v0_1.py:26`) is a plain class attribute, not a `tastypie.fields.*`
  instance -- tastypie's field-discovery metaclass only picks up declared
  `ApiField` instances, so this attribute is inert.
  `test_get_list`/`test_get_single`
  (`corehq/apps/api/tests/test_user_resources.py:90-122,125-157`) assert the
  exact response dict for a created user and neither includes a `type` key.
  The spec's `MobileWorker` schema has no `type` property.

## bulk-user/v1 (`bulk-user.rst`)

- **`offset` is double-applied and returns empty results for any value greater
  than 0.** `bulk-user.rst:75-83` documents `offset` as an ordinary
  paginate-with-`limit` parameter and gives a worked example
  (`offset=200`, third page of 100). `BulkUserResource.obj_get_list`
  (`corehq/apps/api/resources/v0_5.py:211-233`) reads `offset`/`limit` from
  `bundle.request.GET` and passes them straight to `user_es_call`
  (`v0_5.py:161-169`) as `start_at`/`size`, so Elasticsearch already returns a
  single, correctly-offset page. `BulkUserResource.Meta`
  (`v0_5.py:194-199`) inherits `CustomResourceMeta`, which never sets
  `paginator_class` (`corehq/apps/api/resources/meta.py:76-82`), so tastypie
  falls back to its real, default `Paginator`
  (`tastypie/resources.py:80,1349`). That paginator reads the *same* `offset`
  GET parameter again and re-slices the already-short page
  (`Paginator.get_slice`, `tastypie/paginator.py:109-116`:
  `self.objects[offset:offset+limit]`). For `offset=0` this is harmless (the
  page is already `<= limit` items, so `[0:limit]` is a no-op), but for any
  `offset > 0` the second slice starts past the end of the (already-short)
  page, so `objects` comes back empty even though matching records genuinely
  exist at that position. Neither `TestBulkUserAPI`
  (`corehq/apps/api/tests/test_user_resources.py:1002-1032`, which mocks
  `user_es_call` entirely) nor any other test exercises a non-zero `offset`
  against the real pagination path. The spec's `listUsersBulk` `offset`
  parameter documents this; a human should decide whether to fix it (for
  example, by setting `paginator_class = DoesNothingPaginator`, as
  `UserDomainsResource` and several other resources in this codebase already
  do).
- **`total_count` in the response `meta` is not the domain's real user count
  -- it is capped at the size of the current page.** `bulk-user.rst`'s sample
  output (`:39-45`) shows `"total_count": 304` alongside `"limit": 20`,
  implying `total_count` reflects the full matching set. `Paginator.get_count`
  (`tastypie/paginator.py:118-126`) tries `self.objects.count()` and falls
  back to `len(self.objects)` on `AttributeError`/`TypeError`; `self.objects`
  here is a plain Python list of `namedtuple`s (`BulkUserResource.to_obj`,
  `v0_5.py:185-192`), which has no `.count()`, so `get_count` returns
  `len(self.objects)` -- the length of the single Elasticsearch page already
  fetched (at most `limit` items), not a true domain-wide count. The spec's
  `BulkUserList` schema documents the real, page-capped meaning of
  `total_count`.
- **The `q` query-string filter was previously broken but is fixed in the
  current code -- checked per the task brief's instruction, nothing to flag.**
  `UserES.set_query()` returns a new, cloned query rather than mutating in
  place; an earlier version of `obj_get_list` discarded that return value
  (`query.set_query(...)` with no assignment), so every `q` value was silently
  ignored and the unfiltered result set was returned regardless. Current code
  (`v0_5.py:168`) correctly assigns the result: `query =
  query.set_query({"query_string": {"query": q}})`.
  `TestBulkUserESCall.test_q_filters_to_matching_user`/`test_q_none_returns_all_users`
  (`corehq/apps/api/tests/test_user_resources.py:1125,1136`) cover this
  directly against real Elasticsearch. **Negative finding, included for
  completeness.**
- **A GET on `/a/{domain}/api/bulk-user/v1/{id}/` is nominally allowed
  (`Meta.detail_allowed_methods = ['get']`, `v0_5.py:197`) but is not actually
  implemented, and would return an uncaught 500.** `BulkUserResource` never
  overrides `obj_get`; the base `tastypie.resources.Resource.obj_get`
  (`tastypie/resources.py:1172-1182`) unconditionally `raise
  NotImplementedError()`. `get_detail`'s exception handling only special-cases
  `ObjectDoesNotExist`/`MultipleObjectsReturned`
  (`tastypie/resources.py:1362-1383`); `NotImplementedError` falls through to
  `wrap_view`'s generic `except Exception` -> `_handle_500`
  (`tastypie/resources.py:250-265,291-315`). `bulk-user.rst` never documents a
  detail endpoint at all. Not modelled in the spec (the task brief scopes this
  resource to the list operation only); recorded here so a later task does not
  assume a working detail GET exists.

## sso/v1 (`sso.rst`)

- **The response is not "identical to the List User API or List Web User
  API," as `sso.rst:26` claims.** `SingleSignOnResource.post_list`
  (`corehq/apps/api/resources/v0_4.py:260-297`) dehydrates the authenticated
  user with a freshly-constructed `v0_1.CommCareUserResource()` or
  `v0_1.WebUserResource()` (`v0_4.py:288-291,295-296`) -- the *base* classes
  in `v0_1.py`, not the `v0_5` subclasses (`v0_5.CommCareUserResource`,
  `v0_5.WebUserResource`) that actually back `listMobileWorkers`/
  `getMobileWorker` and `listWebUsers`/`getWebUser`. Concretely absent from
  the mobile-worker-shaped response: `primary_location`, `locations`,
  `require_account_confirmation`, `send_confirmation_email_now` (all declared
  only on `v0_5.CommCareUserResource`, `v0_5.py:242-245`). Absent from the
  web-user-shaped response: `user_data`, `primary_location_id`,
  `assigned_location_ids`, `profile`, `tableau_role`, `tableau_groups`,
  `is_active_in_domain` (all declared only on `v0_5.WebUserResource`,
  `v0_5.py:473-481`). Additionally, `resource_uri` is always the empty string
  in both SSO shapes -- `v0_1.CommCareUserResource`/`v0_1.WebUserResource`
  never override `get_resource_uri`, unlike their `v0_5` counterparts
  (`v0_5.py:257-268,524-532`), which always compute a real URL. The spec's
  `SsoMobileWorker`/`SsoWebUser` schemas (`components/schemas/sso.yaml`)
  document the real, narrower shape instead of reusing `MobileWorker`/
  `WebUser` wholesale.
- **The 400 for a missing `username`/`password` is plain text, not the shared
  JSON `{"error": ...}` shape used by every other 400 in this spec.**
  `v0_4.py:274-278` returns Django's own `HttpResponseBadRequest('Missing
  required parameter: username')` (or `password`) directly -- a bare Django
  `HttpResponse` subclass, not anything built through tastypie's
  `error_response`/`wrap_view` machinery, so it carries Django's default
  `text/html` content type over a literal, unwrapped string body.
  `sso.rst` documents no error responses at all. The spec's `authenticateUser`
  `400` documents this exact shape.
- **No 401 is reachable for this operation at all.** `SSOAuthentication`
  (`corehq/apps/api/resources/auth.py:63-64`) is a bare `pass`, so it inherits
  tastypie's base `Authentication.is_authenticated`
  (`tastypie/authentication.py:54-60`), which unconditionally returns `True`
  -- tastypie's own auth layer (`tastypie/resources.py:557-572`) can therefore
  never reject a request to this endpoint. Every credential check happens by
  hand inside `post_list` and resolves to 400 (missing field) or 403 (bad
  credentials/wrong user type) instead. The spec's `authenticateUser` `401`
  response documents this explicitly rather than pretending a real 401 body
  exists, since the shared test `test_every_operation_declares_401_and_403`
  requires the key regardless.
- **No credential is echoed back in the response.** Checked specifically per
  the task brief's instruction. `v0_1.CommCareUserResource` and
  `v0_1.WebUserResource` (`corehq/apps/api/resources/v0_1.py:25-158`) declare
  the identical field set already checked for their `v0_5` counterparts in
  the `user/v1 and web-user/v1` section above -- no `password` field on
  either. **Nothing to flag; negative finding, included for completeness.**

## user_domains/v1 (`user-domain-list.rst`)

- **The response `meta` shape does not match the documented sample at
  all -- only `total_count` is real.**
  `user-domain-list.rst:29-36`'s sample response shows a full
  `limit`/`offset`/`next`/`previous`/`total_count` pagination object.
  `UserDomainsResource.Meta.paginator_class = DoesNothingPaginator`
  (`corehq/apps/api/resources/v0_5.py:1100`); `DoesNothingPaginator.page()`
  (`corehq/apps/api/resources/pagination.py:42-47`) returns only
  `{"objects": self.objects, "meta": {"total_count": self.get_count()}}` --
  no `limit`, `offset`, `next`, or `previous` keys are ever present, and
  `self.objects` (the full result of `get_object_list`,
  `v0_5.py:1119-1141`) is never sliced by the paginator. In other words,
  **this endpoint returns every matching domain in a single, unpaginated
  response**, regardless of any `limit`/`offset` query parameter a client
  might send (both are silently ignored -- `DoesNothingPaginator.page()`
  never reads `self.request_data`). The spec's `UserDomainList` schema
  documents the real, `total_count`-only meta shape, and `listUserDomains`
  declares no `limit`/`offset` parameters.
- **No 403 is reachable for this operation at all.**
  `LoginAuthentication.is_authenticated`
  (`corehq/apps/api/resources/auth.py:75-79`) delegates to `_auth_test`
  (`auth.py:81-95`), which always collapses its result to a plain Python
  `bool` (`return response is PASSED_AUTH`) -- unlike
  `LoginAndDomainAuthentication._auth_test` (`auth.py:114-135`, used by every
  permission-gated resource in this spec), it never returns the actual
  `HttpResponse` a failed auth decorator produced. Tastypie's own
  `is_authenticated` (`tastypie/resources.py:557-572`) only preserves a
  non-401 status when the authentication backend's return value is itself an
  `HttpResponse` instance; a plain `False` always becomes a 401
  (`http.HttpUnauthorized()`). `get_object_list`
  (`corehq/apps/api/resources/v0_5.py:1116-1141`) enforces no permission or
  domain-membership check of its own either -- the only non-200 outcomes are
  401 (auth failure) and 400 (invalid `feature_flag`). The spec's
  `listUserDomains` `403` response documents this explicitly rather than
  claiming a real 403 body exists, since `test_every_operation_declares_401_and_403`
  requires the key regardless. This same mechanism (a `LoginAuthentication`
  instance whose `_auth_test` discards the real response) is shared by
  `getIdentity` in `paths/web-user.yaml`, whose already-committed `403`
  response describes a genuine-looking forbidden path from the
  `require_domain=False` decorator branch
  (`corehq/apps/domain/decorators.py:308-329`) -- by the same trace, that
  decorator's `HttpResponseForbidden()` return value would also be discarded
  by `LoginAuthentication._auth_test`'s boolean coercion and surface as a 401,
  not a 403. Not corrected here (`web-user.yaml` is Task 11's file, out of
  this task's scope) -- flagged for a human to verify.
- **No 429 is reachable for this operation at all.**
  `UserDomainsResource.Meta` (`v0_5.py:1095-1100`) is a plain `object`, not
  `CustomResourceMeta`, so it never sets `throttle`; tastypie's default
  `BaseThrottle.should_be_throttled` (`tastypie/throttle.py:51-61`) always
  returns `False`. Same situation, and same treatment, as `getIdentity`'s
  `429` in `paths/web-user.yaml`.

## location/v1, location/v2, location_type/v1 (`locations-v1.rst`, `locations-v2.rst`, `location-types.rst`)

- **`location_type/v1` is not actually method-restricted at all -- its
  effective GET-only behavior comes from a different mechanism than
  `location/v1`'s, and one write attempt reaches a different status than
  either method_check (405) or the shared PermissionDenied path (bare 403).**
  Confirmed by direct introspection
  (`v0_5.LocationTypeResource()._meta.list_allowed_methods` /
  `.detail_allowed_methods` both evaluate to
  `['get', 'post', 'put', 'delete', 'patch']` -- tastypie's full default,
  since `LocationTypeResource.Meta` (`v0_5.py:29-46`) never sets
  `allowed_methods`/`list_allowed_methods`/`detail_allowed_methods` at all).
  Contrast `v0_5.LocationResource.Meta`, which explicitly sets
  `allowed_methods = ['get']` (`v0_5.py:77`), confirmed to actually produce
  `list_allowed_methods = detail_allowed_methods = ['get']`. So a non-GET
  request to `location_type/v1/` passes tastypie's `method_check`
  (`tastypie/resources.py:521-555`) and reaches the normal
  create/update/delete flow, unlike `location/v1`, which 405s before that
  point. What actually stops the write is `Meta.authorization`, which neither
  `LocationTypeResource` nor any ancestor overrides, so it defaults to
  `tastypie.authorization.ReadOnlyAuthorization()` (confirmed by
  introspection: `type(lt._meta.authorization)` is
  `ReadOnlyAuthorization`). `ReadOnlyAuthorization.create_detail`/
  `update_detail`/`delete_detail` (`tastypie/authorization.py:107-120`) each
  raise `tastypie.exceptions.Unauthorized`. The default
  `ModelResource.obj_create`/`obj_update`/`obj_delete` (which
  `LocationTypeResource` does not override) route through `save()`
  (`tastypie/resources.py:2392-2410`), which calls
  `authorized_create_detail`/`authorized_update_detail`
  (`tastypie/resources.py:651-663, 677-689`); those catch `Unauthorized` and
  call `unauthorized_result` (`tastypie/resources.py:610-611`), which raises
  `ImmediateHttpResponse(response=http.HttpUnauthorized())` -- a bare, empty
  **401**. This propagates to `wrap_view`'s generic exception handler
  (`tastypie/resources.py:250-254`), which special-cases any exception with an
  `HttpResponse`-typed `.response` attribute and returns it directly. Net
  effect: a POST/PUT/PATCH/DELETE to `location_type/v1/` reaches a bare empty
  401, not the 405 `location/v1` produces for the same verbs, not the bare 403
  a permission failure produces elsewhere in this API, and not a 500. Neither
  `location-types.rst` nor the task brief's method table describes this
  correctly (the brief assumed `location_type` was method-restricted the same
  way `location/v1` is); the spec documents only the real, working GET
  operations for `location_type/v1`, matching the reST docs, and omits any
  write operations rather than documenting ones that only ever fail.
- **v2's `PUT` on a nonexistent `location_id` is a 400, never a 404,** and the
  detail `GET`/bulk-`PATCH`-update code paths reach three different outcomes
  for "location not found" despite sharing the same lookup helper.
  `v0_6.LocationResource.obj_update` (`v0_6.py:90-99`) fetches with a plain
  `SQLLocation.objects.get(location_id=..., domain=...)` and converts a miss
  directly to `LocationAPIError` (`v0_6.py:18-22`, a
  `tastypie.exceptions.BadRequest` subclass) -- never tastypie's own
  `NotFound`, the only exception `put_detail`
  (`tastypie/resources.py:1502`) catches to fall back to `obj_create`. So the
  miss reaches `wrap_view`'s `except (BadRequest, fields.ApiFieldError)`
  (`tastypie/resources.py:244-246`) and becomes a 400 with the standard
  `{"error": "Could not update: could not find location with given ID <id> on
  the domain."}` body -- confirmed verbatim by
  `corehq/apps/locations/tests/test_api_resources.py:401-430`
  (`test_patch_list_missing_location_id`, which exercises the identical
  `obj_update` call from the bulk-PATCH path and asserts exactly this message
  and a 400 status). `replaceLocationV2`'s GET sibling
  (`getLocationV2`) does 404 correctly, since GET is not overridden and goes
  through tastypie's default `get_detail`
  (`tastypie/resources.py:1362-1383`), which catches
  `SQLLocation.DoesNotExist` (a real `ObjectDoesNotExist`) and returns a bare
  `http.HttpNotFound()`. `locations-v2.rst` never states what happens for a
  missing `location_id` on either endpoint. The spec's `replaceLocationV2`
  omits `404` entirely (with an inline comment in `paths/location-v2.yaml`)
  and documents the 400 instead; `getLocationV2` keeps its genuine, bare-body
  404.
- **v2's detail `PUT` will 400 if the client includes `location_id` in the
  request body, undocumented by `locations-v2.rst`.** `obj_update`
  (`v0_6.py:90-99`) resolves the target id with
  `location_id = kwargs.get('location_id') or bundle.data.pop('location_id')`.
  For the URL-based detail PUT, `kwargs['location_id']` (from the URL) is
  always truthy, so Python's `or` short-circuits and
  `bundle.data.pop('location_id')` is never evaluated -- any `location_id` key
  in the body is never removed from `data`. `_update`'s end-of-method leftover
  check (`v0_6.py:134-136`, `if len(data): raise LocationAPIError(...
  "Invalid fields were included in request: [...]")`) then fires, since
  `location_id` is not among the fields `_update` recognizes. (The bulk-PATCH
  path is different: there, `kwargs.get('location_id')` is falsy because the
  list endpoint's URL kwargs never include a `location_id`, so the `or`
  falls through to `bundle.data.pop('location_id')`, which is exactly how a
  bulk item signals "this is an update" -- `location_id` in the body is
  required and expected there, not rejected.) `locations-v2.rst`'s "Editable
  Fields" table for PUT (`:175-196`) simply omits `location_id` without
  warning that including it is actively rejected. The spec's `LocationUpdate`
  schema documents this in its description and does not list `location_id` as
  a property.
- **v2's bulk `PATCH` never produces the group resource's
  ids-and-errors-mixed-positionally array -- a batch either fully succeeds
  (array of ids) or fully fails (single `{"error": ...}` object), never
  both.** The task brief suggested this resource's bulk PATCH "returns
  surprising shapes" the way the group resource's does and pointed at
  `patch_list_replica`'s `obj_limit` handling as the mechanism to trace;
  tracing it shows the two resources diverge. `patch_list_replica`
  (`corehq/apps/api/resources/__init__.py:172-205`) only ever substitutes an
  error string into the per-item array slot inside its `except AssertionError`
  handler (`:199-201`) -- for the group resource this fires because its
  `obj_create`/`obj_update` raise bare `assert` statements
  (`corehq/apps/api/resources/v0_5.py:753,759`). `v0_6.LocationResource`'s
  entire write path (`_update`, `_validate_new_parent`,
  `_validate_unique_among_siblings`, `_get_parent_location`, `obj_create`,
  `obj_update`) raises only `LocationAPIError` (a `BadRequest`, not an
  `AssertionError`) for every validation failure; there is no bare `assert`
  anywhere in `v0_6.py`. A `LocationAPIError` from any item is never caught by
  `patch_list_replica`'s per-item `try/except AssertionError`
  (`v0_6.py:166-171` calls `create_or_update`, wrapped by
  `patch_list_replica` at `:197-198`) -- it propagates straight out of the
  loop, past the `@atomic` decorator on `patch_list` (`v0_6.py:164`, which
  rolls back on the way out), to `wrap_view`'s `except (BadRequest, ...)`,
  which converts it to a single `{"error": ...}` 400 object. Confirmed by
  `corehq/apps/locations/tests/test_api_resources.py:377-430`
  (`test_patch_list_is_atomic` asserts 400 and that nothing was created;
  `test_patch_list_missing_location_id` asserts
  `response.json() == {'error': "Could not update: ..."}"`, not an array).
  The `obj_limit` check itself (`patch_list_replica:191-192`,
  `v0_6.LocationResource.patch_limit = 100`, `v0_6.py:27`) also raises a plain
  `BadRequest` before any item is processed, for the same single-object 400
  shape. The array shape (`patch_list_replica:204`,
  `[bundle.data['_id'] for bundle in bundles_seen]`) is therefore reachable
  **only on full success** for this resource -- the ambiguous
  id-or-error-string array documented for `bulkUpdateGroups` in
  `paths/group.yaml` cannot occur here. The spec's
  `bulkCreateOrUpdateLocationsV2` documents a clean array-of-ids `202` and a
  single-object `{"error": ...}` `400`, explicitly noting the contrast with
  the group resource.
- **v2's `parent_location_id` is an empty string when a location has no
  parent, not null -- inconsistent with v1's `parent`, which is null in the
  same situation.** `v0_6.LocationResource.dehydrate`
  (`v0_6.py:71-75`) sets `bundle.data['parent_location_id'] = ''` in the
  no-parent branch. Confirmed by
  `corehq/apps/locations/tests/test_api_resources.py:167`
  (`"parent_location_id": ""` for `location1`, which has no parent).
  `locations-v2.rst:64-66` describes the field only as "The UUID of the
  location's direct parent," with no mention of the no-parent case.
  `LocationV2`'s `parent_location_id` in the spec is typed as a plain
  (non-nullable) string with this behavior called out explicitly.
- **v1's `location_type` and `parent` fields, and v2's absence of them, were
  verified by direct introspection, not assumed from the `Meta.fields`
  declaration alone.** `v0_6.LocationResource.Meta.fields`
  (`v0_6.py:39-48`) is a fresh set literal on a `class Meta:` with no base
  class, so it does not inherit `v0_5.LocationResource.Meta`'s `fields` list
  -- but `location_data`, `location_type`, and `parent` are also declared as
  manually-attached `fields.X(...)` class attributes on `v0_5.LocationResource`
  (`v0_5.py:68-70`), which Python inheritance *does* carry onto
  `v0_6.LocationResource` regardless of `Meta`. Introspecting
  `v0_6.LocationResource().fields.keys()` directly resolves the ambiguity:
  the result is exactly the 8 keys in `v0_6.py`'s `Meta.fields` (`domain,
  last_modified, latitude, location_data, location_id, longitude, name,
  site_code`) -- `location_type` and `parent` are genuinely absent, meaning
  `Meta.fields` does filter out inherited manually-declared fields too, not
  just introspected model fields. `location_type_code`/`location_type_name`/
  `parent_location_id` reach the response only via the `dehydrate` override
  writing directly into `bundle.data`, confirmed against
  `test_api_resources.py:157-213`'s exact-dict assertions. Not a
  discrepancy against the reST docs (v2's sample matches), but recorded since
  it contradicts what the `Meta.fields` docstring convention might suggest to
  a future task about how `Meta.fields` and inherited manual fields interact.
- **The v2 `last_modified.gte`/`.gt`/`.lt`/`.lte` filters accept a timezone
  offset or literal `Z`, unlike case/v1's `*_start`/`*_end` filters, which
  reject one with a 400 (`validate_date`).** Traced directly per the task
  brief's instruction not to copy either existing precedent.
  `v0_6.LocationResource.build_filters` (`v0_6.py:56-69`) does no date parsing
  of its own -- it only rewrites the dotted key to a double-underscore ORM
  lookup (`last_modified__gte`) and hands the raw query-string value straight
  to `SQLLocation.objects.filter(...)`, a real Django ORM filter against
  `last_modified`, a genuine `models.DateTimeField(auto_now=True)`
  (`corehq/apps/locations/models.py:372`). Django's
  `DateTimeField.get_prep_value` (`django/db/models/fields/__init__.py:
  1186-1190`) calls `to_python`, which tries
  `django.utils.dateparse.parse_datetime` first
  (`django/db/models/fields/__init__.py:1621-1630`) -- this parses a bare
  date, a naive datetime, or one with a UTC offset or trailing `Z`
  indifferently, raising nothing for any of them. The
  naive-vs-aware reconciliation branch that would otherwise matter
  (`get_prep_value`, `django/db/models/fields/__init__.py:1198-1200`, guarded
  by `settings.USE_TZ and timezone.is_naive(value)`) never fires either way
  because `settings.USE_TZ = False` (`settings.py:57`) -- so an
  offset-bearing value is passed straight through, unconverted, to
  `adapt_datetimefield_value` (`django/db/backends/postgresql/operations.py:
  350-351`, a no-op), and Postgres compares it against the naive
  `timestamp without time zone` column using its own session timezone rules.
  No exception is ever raised for an offset value on this code path -- a
  materially different outcome from case/v1's `validate_date`
  (`corehq/apps/api/es.py:277-285`), which checks the string against four
  fixed `strptime` formats, none with `%z`, and explicitly rejects an offset
  with a 400. **Caveat: this was traced entirely from Django/tastypie source,
  not confirmed with a live request in this environment** -- no Postgres or
  Elasticsearch service was reachable here (`docker ps` showed no running
  containers, and the project's own Postgres was listening on a port the
  configured `localsettings.py` `DATABASES` setting doesn't point at), so
  `corehq/apps/locations/tests/test_api_resources.py`'s existing
  `test_api_filters` cases (none of which include an offset) could not be
  extended and re-run to double-check this conclusion empirically. A human
  should confirm with a live database before treating this as settled.
- **`location/v1` and `location_type/v1`'s 403 body is empty, not the shared
  `{"error": ...}` shape `paths/group.yaml` and `paths/case-v1.yaml` point at
  for the identical `RequirePermissionAuthentication` class.** Both
  `GroupResource` (`corehq/apps/api/resources/v0_4.py:253`) and all three
  location resources use `RequirePermissionAuthentication`, which delegates to
  `LoginAndDomainAuthentication._auth_test` (`corehq/apps/api/resources/auth.py
  :114-135`): a failed permission check raises Django's `PermissionDenied`
  (`require_permission_raw`, `corehq/apps/users/decorators.py:34-54`), caught
  directly by `_auth_test` and converted to a bare `HttpResponseForbidden()` --
  no body, no JSON. This exact mechanism and finding were already established
  for `getForm`/`listForms` earlier in this file (see the form/v1 section);
  this resource shares the identical authentication class and code path, so
  the same conclusion applies here rather than being re-derived from scratch.
  `paths/group.yaml`'s and `paths/case-v1.yaml`'s `403` responses, by
  contrast, point at the shared `Forbidden` ref (a JSON `{"error": ...}`
  body) despite using the same `RequirePermissionAuthentication` class --
  those two do not appear to have been verified against the body, only
  against the status code. Out of scope for this task to fix (both are
  earlier tasks' committed files), but flagged here since a reviewer
  comparing this task's location paths against those precedents will
  otherwise wonder why they disagree. This task's `location-v1.yaml`,
  `location-v2.yaml`, and `location-type.yaml` all document the bare-empty
  403 instead.
- **Three additional 401/403-shaped gates exist ahead of the standard
  tastypie auth flow, applicable to every location (and every other
  `HqBaseResource`-based) operation, and were not modeled as separate
  responses since their JSON shape does not differ from the documented 401.**
  `BaseLocationsResource.dispatch` (`v0_5.py:19-23`) checks
  `domain_has_privilege(request.domain, privileges.LOCATIONS)` before calling
  `super().dispatch()`, raising a bare `HttpResponseForbidden()` if the domain
  lacks the Locations privilege -- this is the second cause of the bare-403
  described above, alongside the permission-check failure, and both are
  documented together in the spec since they're bodily identical.
  `HqBaseResource.dispatch` (`corehq/apps/api/resources/__init__.py:132-151`),
  a base class of every location resource, additionally short-circuits with a
  401 JSON body of `{"error": "API access has been temporarily cut off due to
  too many requests. To re-enable, please contact support."}` if the
  `API_BLACKLIST` feature toggle is enabled for the request (`:133-139`), and
  a different 401 JSON body,
  `{"error": "Your current subscription does not have access to this
  feature"}`, if the domain lacks the `API_ACCESS` privilege (`:140,147-151`).
  Both are structurally compatible with the shared `Unauthorized` response's
  `{"error": ...}` schema (just different message text), so the spec's shared
  `401` ref already covers them without a resource-specific override; noted
  here only because the first of the two is semantically a rate-limit
  response (its message talks about "too many requests") but is a 401, not
  the 429 the shared `TooManyRequests` response would suggest -- a client
  branching on status code alone would miss it.

## fixture/v1, lookup_table/v1, lookup_table_item/v1 (`fixture.rst`)

- **`fixture/v1` is not method-restricted at all, but its writes are broken
  by a different mechanism than `location_type/v1`'s.** Confirmed by direct
  introspection: `FixtureResource()._meta.list_allowed_methods` and
  `.detail_allowed_methods` both evaluate to `['get', 'post', 'put', 'delete',
  'patch']` (tastypie's full default), because `FixtureResource.Meta`
  (`corehq/apps/fixtures/resources/v0_1.py:91-95`) sets `authentication`,
  `object_class`, `resource_name`, and `limit`, but never
  `allowed_methods`/`list_allowed_methods`/`detail_allowed_methods`. So a
  non-`GET` request passes `method_check` (`tastypie/resources.py:521-555`)
  and reaches the normal create/update/delete flow. Unlike
  `location_type/v1`, `FixtureResource` is a plain `tastypie.resources.
  Resource` subclass (via `HqBaseResource`), not a `ModelResource`, and it
  overrides only `obj_get`/`obj_get_list`/`detail_uri_kwargs`
  (`v0_1.py:59-89`) -- it never overrides `obj_create`/`obj_update`/
  `obj_delete`, so those fall through to the base `Resource`'s versions
  (`tastypie/resources.py:1198-1247`), which unconditionally `raise
  NotImplementedError()`. Because this is a plain `Resource`, not a
  `ModelResource`, `Meta.authorization` (`ReadOnlyAuthorization`, inherited
  from `CustomResourceMeta`, confirmed by introspection) is never consulted at
  all -- `ReadOnlyAuthorization.create_detail`/`update_detail`/`delete_detail`
  are only ever called from `ModelResource.obj_create`/`obj_update`/
  `obj_delete` (`tastypie/resources.py:2232-2387`), which `FixtureResource`
  does not use. `NotImplementedError` has no `.response` attribute, so
  `wrap_view`'s generic exception handler (`tastypie/resources.py:250-270`)
  falls through to `_handle_500` (`:291-315`), and
  `get_response_class_for_exception` (`:274-289`) does not special-case
  `NotImplementedError`, so it returns `http.HttpApplicationError` -- a genuine
  **500**, not the bare 401 `location_type/v1` produces for the same verbs
  and not a 405. The spec documents only the real, working `GET` operations
  for `fixture/v1`, matching `fixture.rst`, and omits any write operations
  rather than documenting ones that only ever crash.
- **`lookup_table/v1` and `lookup_table_item/v1`'s `Meta.authorization =
  ReadOnlyAuthorization()` (inherited, unmodified) is likewise never
  consulted, for the same "plain `Resource`, custom `obj_create`/`obj_update`/
  `obj_delete`" reason -- but unlike `fixture/v1`, these two resources DO
  implement working custom versions of all three
  (`v0_1.py:193-236,360-368,370-409`), so their declared
  `list_allowed_methods = ['get', 'post']` /
  `detail_allowed_methods = ['get', 'put', 'delete']` (`v0_1.py:243-244,
  416-417`, confirmed by introspection) are the real, enforced method set.
  Noted only so a reader does not assume `ReadOnlyAuthorization` on these two
  classes means anything -- it is dead configuration.
- **`fixture.rst:122-123` states "Permission Required: Edit Apps" for the
  Excel upload API, but the code requires Edit Data, not Edit Apps.**
  `upload_fixture_api`/`fixture_api_upload_status` are both gated by
  `require_can_edit_fixtures` (`corehq/apps/fixtures/dispatcher.py:9-13`),
  which composes `require_permission(HqPermissions.edit_data)` with
  `requires_privilege_with_fallback(privileges.LOOKUP_TABLES)` -- there is no
  `edit_apps` check anywhere in this path.
  `_get_fixture_upload_args_from_request` (`corehq/apps/fixtures/views.py
  :553-556`) additionally re-checks `HqPermissions.edit_data.name` explicitly,
  reinforcing that Edit Data, not Edit Apps, is the real requirement.
- **`uploadFixtureExcel`'s and `getFixtureUploadStatus`'s HTTP status is
  always 200, regardless of outcome.** `upload_fixture_api`
  (`corehq/apps/fixtures/views.py:417-426`) does `return
  JsonResponse(upload_fixture_api_response.get_response())` with no `status=`
  argument, so the response's real status (Django defaults `JsonResponse` to
  200) never reflects `UploadFixtureAPIResponse.code`'s 402/405 values
  (`views.py:377-393`); those exist only inside the body. Likewise
  `fixture_api_upload_status` (`views.py:429-464`) calls `json_response(...)`
  (`dimagi/utils/web.py:76-84`) without a `status_code` argument on every one
  of its branches, including the `TaskFailedError` branch, so a failed queued
  upload is still reported as HTTP 200 with `{"error": true, ...}` in the
  body. `fixture.rst:156-176`'s "Response" table documents `code` values of
  200/402/405 in a way that reads as if they were the transport status, with
  no statement that the transport status is always 200 regardless.
- **`getFixtureUploadStatus` has no reachable 404 for any `download_id`,
  including one that was never issued.** `get_download_context`
  (`corehq/ex-submodules/soil/util.py:73-107`) calls `DownloadBase.get
  (download_id)`; if that returns `None` (unknown id), it falls back to a
  fresh, task-less `DownloadBase(download_id=download_id)` rather than
  raising. `get_task_status(None, ...)` (`corehq/ex-submodules/soil/progress.
  py:144-154`) then takes the `if not task:` branch, which reports
  `is_ready=False`/`failed=False` -- indistinguishable from a real task still
  running. A caller polling a mistyped or expired `download_id` gets an
  indefinite "in progress" response, never an error.
- **`createLookupTableItem`'s and `replaceLookupTableItem`'s 404 (for an
  unknown `data_type_id`) is tastypie's generic-exception-handler canned
  body, not a resource-specific message, even though the exception raised
  ("Lookup table not found") suggests one.** `LookupTableItemResource.
  obj_create` (`v0_1.py:370-388`) raises tastypie's own `NotFound('Lookup
  table not found')` at `v0_1.py:377` when the referenced lookup table does
  not exist. On `POST` (`createLookupTableItem`), `post_list`
  (`tastypie/resources.py:1385-1407`) has no `try`/`except` around its call
  to `obj_create`, so the exception propagates uncaught into `wrap_view`'s
  generic handler, which maps `NotFound` to a 404
  (`get_response_class_for_exception`, `:274-289`) via `_handle_500`
  (`:291-315`) -- producing the same canned `{"error_message": "Sorry, this
  request could not be processed. Please try again later."}` body used for
  any uncaught exception in production, discarding the resource's own message
  text entirely. On `PUT` (`replaceLookupTableItem`) against an unknown
  `lookup_table_item_id`, the same thing happens one level deeper: `obj_update`
  (`v0_1.py:390-409`) raises `NotFound` for the missing row, which `put_detail`
  (`tastypie/resources.py:1467-1511`) correctly catches and retries via
  `obj_create` -- but if *that* also raises `NotFound` (because `data_type_id`
  is also invalid), nothing catches the second exception, since `put_detail`'s
  `except` only wraps the first `obj_update` call. Net effect: two operations
  on this resource can 404, and both do so through the same canned,
  non-resource-specific path -- never through a clean, resource-owned
  not-found response the way `deleteLookupTableItem`'s 404 does.
- **`replaceLookupTable`'s and `replaceLookupTableItem`'s `PUT` against a
  nonexistent id does not 404 -- it silently creates an unrelated new object
  under a different, server-generated id.** Both resources' `obj_update`
  (`v0_1.py:205-218,390-409`) raise tastypie's `NotFound` for an unknown
  `pk`; `put_detail` (`tastypie/resources.py:1467-1511`) catches exactly that
  exception and falls back to calling `obj_create` with the *same submitted
  body*. Neither resource's `obj_create` (`v0_1.py:193-203,370-388`) makes any
  use of the URL's `pk` -- `LookupTableResource.obj_create` only checks
  whether the submitted `tag` is already taken, and
  `LookupTableItemResource.obj_create` only checks that `data_type_id`
  references an existing table. So a `PUT` to
  `/api/lookup_table/v1/{nonexistent_id}/` (or the equivalent for
  `lookup_table_item`) with an otherwise-valid body succeeds, returning 201,
  and creates a brand-new object at a new id that has nothing to do with the
  id in the URL. This is the same tastypie fallback mechanism already
  documented for `replaceGroup` in `paths/group.yaml`, but unlike that case
  (which falls through to an uncaught 500 because `Group.obj_create` uses
  Couch and hits a different failure mode), this fallback actually succeeds
  here, silently masking what looks like a "the id you asked for doesn't
  exist" error as a success.
- **`createLookupTable`'s, `replaceLookupTable`'s, `createLookupTableItem`'s,
  and `replaceLookupTableItem`'s validation-failure 400 is a bare JSON array
  of strings, not an object at all -- a third distinct 400 shape alongside
  the `{"error": ...}` and `{"error_message": ...}` shapes already documented
  elsewhere in this file.** Both resources declare a
  `validate_deserialized_data` attribute (a `JSONSchemaValidator` instance,
  `v0_1.py:133-159,300-336`). `HqBaseResource.alter_deserialized_detail_data`
  (`corehq/apps/api/resources/__init__.py:153-167`) calls it and, on a Django
  `ValidationError`, does `raise ImmediateHttpResponse(self.error_response
  (request, error.messages))` -- passing the validator's `error.messages`
  (already a plain list of strings; `JSONSchemaValidator.__call__`,
  `corehq/util/validation.py:51-67`, raises `ValidationError(django_errors)`
  where `django_errors` is a list of single-message `ValidationError`s)
  directly as the "errors" argument. `error_response`
  (`tastypie/resources.py:1264-1299`) serializes that argument as-is with no
  wrapping object of any kind, defaulting to a 400 status. A client that
  branches on `body.error` or `body.error_message` to extract a validation
  message will get neither key -- the message is `body[0]`, `body[1]`, etc.
- **`deleteLookupTable`'s and `deleteLookupTableItem`'s successful delete
  returns 202 Accepted, not the 204 No Content tastypie's own `delete_detail`
  docstring and `paths/group.yaml`'s `deleteGroup` both describe as the
  default.** Both resources' `obj_delete` (`v0_1.py:176-184,360-368`) end
  with `return ImmediateHttpResponse(response=HttpAccepted())`
  (`tastypie/http.py:17-18`: `HttpAccepted.status_code = 202`), raised as an
  exception rather than returned normally. `delete_detail`
  (`tastypie/resources.py:1525-1542`) only ever reaches its own `return
  http.HttpNoContent()` if `obj_delete` returns normally without raising;
  since both `obj_delete` implementations always raise
  `ImmediateHttpResponse` on the success path, that line is dead code for
  these two resources, and the 202 (caught by `wrap_view`'s generic
  `hasattr(e, 'response')` check, `tastypie/resources.py:250-254`) is what
  callers actually see.
- **`lookup_table/v1` and `lookup_table_item/v1` require only the generic
  `access_api` permission, not a specific one, even though `fixture.rst`'s
  read-only fixture API (documented as requiring Edit Apps) and its Excel
  upload API (documented as requiring Edit Apps, actually Edit Data) both
  gate on something specific.** `LookupTableResource.Meta` and
  `LookupTableItemResource.Meta` (`v0_1.py:241-245,414-418`) never set
  `authentication`, so both inherit `CustomResourceMeta.authentication =
  LoginAndDomainAuthentication()` (`corehq/apps/api/resources/meta.py:76-78`),
  which only requires the generic `access_api` permission
  (`corehq/apps/api/resources/auth.py:108-112`) plus domain membership --
  not `edit_apps`, not `edit_data`, and not any lookup-table-specific
  permission. Neither of `fixture.rst`'s "Lookup Table Individual API" or
  "Lookup Table Rows API" sections states a permission requirement at all
  (confirmed: no "Permission Required" field appears in either section), so
  this is not a docs/code disagreement, but it means any domain member with
  API access can create, edit, and delete lookup tables and their rows via
  this API, which is easy to miss without reading the code.
- **`fixtures.v0_6.LookupTableItemResource` is registered at
  `lookup_table_item/v2` but is entirely undocumented by `fixture.rst`, and
  is out of scope for this spec.** `corehq/apps/api/urls.py:191`
  (`fixtures.v0_6.LookupTableItemResource.get_urlpattern('v2')`) registers
  it alongside the `v1` resources this task documents (`urls.py:189-190`).
  `v0_6.LookupTableItemResource` (`corehq/apps/fixtures/resources/v0_6.py`)
  subclasses `v0_1.LookupTableItemResource` and changes exactly one thing:
  `Meta.always_return_data = True`, meaning its `POST`/`PUT` return the full
  serialized row (200/201 with a body) instead of the empty-bodied responses
  `v1` returns. Per the plan, the spec covers what `fixture.rst` covers, so
  `v2` is intentionally left out of `paths/lookup-table.yaml`; flagged here
  rather than silently dropped.
  branching on status code alone would miss it.

## simplereportconfiguration/v1, configurablereportdata/v1 (`list-reports.rst`, `download-report-data.rst`)

- **`listReports`'s and `getReport`'s sample filter objects omit a real
  `type` field.** `dehydrate_filters` (`corehq/apps/api/resources/
  v0_5.py:963-969`) unconditionally emits `type`/`datatype`/`slug` for every
  filter, but both sample objects in `list-reports.rst` (`:65-74,97-114`)
  show only `datatype`/`slug`. The spec's `ReportFilter` schema includes
  `type` as always present.
- **`list-reports.rst`'s own prose and its own sample disagree about valid
  `datatype` values.** `list-reports.rst:37` states a filter's `datatype` is
  one of `"string"`/`"integer"`/`"decimal"`, but the page's second sample
  object (`:110-113`) shows `"datatype": "date"` for a filter named
  `form_date`. The code does not constrain `datatype` at all
  (`dehydrate_filters` copies the value verbatim), so this is not a
  code/docs disagreement so much as the reST page contradicting itself; the
  spec's `ReportFilter.datatype` is not modeled as an `enum` for this reason.
- **`listReports`/`getReport` require no report-specific permission, despite
  neither reST page claiming one.** `SimpleReportConfigurationResource.Meta`
  (`v0_5.py:998-1001`) declares no `authentication` override, so it falls
  back to `CustomResourceMeta.authentication = LoginAndDomainAuthentication()`
  (`corehq/apps/api/resources/meta.py:76-78`) -- login, domain membership,
  and the generic `access_api` permission only. Not a docs/code
  disagreement (neither page states a requirement), but easy to miss when
  comparing against `downloadReportData`'s much narrower access, so noted
  for visibility.
- **`downloadReportData`'s stated permission requirement does not match any
  real `HqPermissions` field.** `download-report-data.rst:21-23` says
  "Permission Required: View Data, Access All Reports". Neither `"View
  Data"` nor `"Access All Reports"` corresponds to an actual field on
  `HqPermissions` (`corehq/apps/users/models.py:190-221`) -- the closest
  matches are `view_data_dict` (an unrelated "data dictionary" permission)
  and `access_all_locations` (unrelated to reports). The resource's real
  authentication is `RequirePermissionAuthentication(HqPermissions.
  view_reports, allow_session_auth=True)` (`v0_5.py:952`) -- a single
  permission, `view_reports` ("View Reports" in the UI), with no
  "access all reports" component at all. The spec's `downloadReportData`
  documents `view_reports` as the real requirement.
- **A malformed `filter_name` value can produce an uncaught 500, not the
  documented behaviour.** Neither reST page discusses filter-value error
  handling. `ConfigurableReportDataResource.obj_get`
  (`v0_5.py:892-917`) calls `_get_report_data` -> `get_filter_values`
  (`corehq/apps/userreports/reports/view.py:82-96`), which re-raises any
  `FilterException` (e.g. an unparsable date on a `-start`/`-end` pair) as
  `UserReportsFilterError`. That exception is not caught anywhere in
  `obj_get`, is not tastypie's `BadRequest`/`NotFound`/`ObjectDoesNotExist`,
  and so reaches `wrap_view`'s generic exception handler
  (`tastypie/resources.py:250-265`), whose
  `get_response_class_for_exception` (`:273-284`) does not recognize it
  either -- the default `http.HttpApplicationError` (500) applies. A client
  sending a bad filter value gets an uncaught 500, not a 400. The spec's
  `downloadReportData` operation description states this; no formal `500`
  response was added (following the precedent of omitting responses the
  spec cannot usefully constrain, e.g. `replaceGroup`'s omitted 404).
- **`ConfigurableReportData`'s `resource_uri` field is real and undocumented.**
  Every tastypie resource adds a `resource_uri` field by default
  (`include_resource_uri`, `tastypie/resources.py:96,161`), not excluded by
  `ConfigurableReportDataResource.Meta` (`v0_5.py:951-954`); this resource's
  own `get_resource_uri` override (`v0_5.py:940-949`) appends the effective
  `offset`/`limit` to it. `download-report-data.rst`'s sample output
  (`:61-98`) has no `resource_uri` key.
- **`ConfigurableReportData.next_page` is an empty string, not `null`, when
  there is no further page.** `_get_next_page`'s `else` branch
  (`v0_5.py:859-860`) `return ""`. `download-report-data.rst` never shows
  the last-page case, so this is undocumented, not contradicted.

## det_export_instance/v1 (`det-exports.rst`)

- **A real detail (`GET .../{id}/`) operation exists, entirely undocumented
  by `det-exports.rst`, which only describes the list endpoint.**
  `DETExportInstanceResource.Meta.detail_allowed_methods = ['get']`
  (`corehq/apps/api/resources/v1_0.py:201`) and `obj_get`
  (`v1_0.py:262-288`) is fully implemented (it even handles both
  `FormExportInstance` and `CaseExportInstance` lookups, and a domain/type
  mismatch). Per the resource-task conventions ("a missing operation for a
  method the code allows" is a defect), the spec documents this as
  `getDETExport`, beyond the task brief's ten listed paths.
- **`resource_uri` is real and undocumented.** Same mechanism as the report
  resources above (`tastypie/resources.py:96,161`); `det-exports.rst`'s
  sample output (`:61-84`) has no `resource_uri` key.
- **`listDETExports`'s response `meta` is undocumented but real, with full
  pagination.** `DETExportInstanceResource.Meta` sets no `paginator_class`
  override (`v1_0.py:198-202`), so it uses tastypie's own default
  `Paginator` (`tastypie/resources.py:80`), not one of the "does nothing"
  paginators the report/application resources use. `limit`/`offset` are
  real and a bad value raises tastypie's `BadRequest` -> the shared
  `{"error": ...}` 400 shape. `det-exports.rst`'s sample output (`:61-84`)
  omits `meta` entirely.

## application/v1, import_app, multimedia upload/status (`application-structure.rst`, `import-app.rst`)

- **`application-structure.rst`'s sample output nests `versions` inside each
  module; the code returns it as a single top-level field of the
  application, not one list per module.** The sample (`:73-105`) shows
  `"modules": [{"case_type": ..., "forms": [...], "versions": [...]}]`.
  `ApplicationResource.versions` (`corehq/apps/api/resources/
  v0_4.py:342,344-359`) is declared directly on the resource and dehydrated
  from `bundle.obj` (the application), never per-module; `dehydrate_module`
  (`v0_4.py:365-404`) builds `name`/`case_type`/`case_properties`/
  `unique_id`/`forms` for a module and never touches `versions`. A client
  following the sample would look for build history in the wrong place
  entirely.
- **`application-structure.rst`'s sample output includes a `case_types` key
  the code cannot produce.** The sample (`:66-72`) shows a top-level
  `"case_types": {"type_of_case...": ["case_prop1", ...]}`.
  `ApplicationResource` declares no `case_types` field anywhere
  (`v0_4.py:332-422`), and `dehydrate` (`:415-422`) only ever returns the
  standard dehydrated fields, or (with `extras=true`) those merged with the
  raw internal doc -- neither path adds a `case_types` key under that name
  at the top level. Following the precedent set for the group resource's
  undocumentable `path` field, the spec's `Application` schema does not
  include `case_types` at all.
- **`resource_uri` is real and undocumented**, same mechanism as the other
  resources in this file (`tastypie/resources.py:96,161`);
  `application-structure.rst`'s sample has no `resource_uri` key.
- **Two real fields per module/form entry are undocumented.** The sample
  module (`:73-105`) has no `unique_id` key, though `dehydrate_module`
  always sets one (`v0_4.py:382`); the sample form (`:77-92`) has no
  `xmlns` or `unique_id` key, though both are always set
  (`v0_4.py:388,397`).
- **`listApplications`/`getApplication` require no application-specific
  permission, contradicting the stated requirement.**
  `application-structure.rst:18-19` says "Permission Required: Edit Apps".
  `BaseApplicationResource.Meta.authentication =
  LoginAndDomainAuthentication(allow_session_auth=True)` (`v0_4.py:324`) --
  login, domain membership, and the generic `access_api` permission only,
  with no `edit_apps` check anywhere in the class. Contrast
  `importApplication`/`uploadApplicationMultimedia`/
  `getMultimediaUploadStatus`, which really do require
  `HqPermissions.edit_apps` (`app_import_api.py:30,85,131`), matching
  `import-app.rst:26`.
- **`ApplicationList`'s `meta.limit` can never be the value
  `application-structure.rst`'s sample shows.**
  `BaseApplicationResource.Meta.paginator_class = DoesNothingPaginatorCompat`
  (`v0_4.py:329`; `corehq/apps/api/resources/pagination.py:50-68`)
  hardcodes `meta.limit` to `null` and `meta.offset` to `0` on every
  response, ignoring the real `limit`/`offset` query parameters entirely.
  `application-structure.rst:51` shows `"limit": 20` in its sample --
  the code cannot produce that value under any query.
- **Two fields on `getMultimediaUploadStatus`'s response are real but
  undocumented by either sample in `import-app.rst`.**
  `BaseMultimediaStatusCache.get_response` (`corehq/apps/hqmedia/
  cache.py:45-56`) always includes `type` (`"zip"` for this endpoint,
  from `BulkMultimediaStatusCache.upload_type`, `cache.py:71`) and
  `is_ready` (a mirror of `complete`). Neither key appears in either the
  "In Progress" (`import-app.rst:235-248`) or "Complete"
  (`:255-284`) sample.
- **`getMultimediaUploadStatus` does not actually have two response shapes
  -- it has one, with values that are zero/empty/null before processing
  finishes.** `import-app.rst` presents "In Progress" and "Complete" as
  distinct shapes (the task brief likewise called for a `oneOf` over them),
  but `BulkMultimediaStatusCache.__init__` (`cache.py:73-79`) initializes
  `total_files`/`processed_files` to `None` and every count/list field to
  `0`/`[]`/empty dicts, and `get_response` (`cache.py:85-99`) always
  includes every one of `matched_count`/`unmatched_count`/`matched_files`/
  `total_files`/`processed_files`/`image_count`/`audio_count`/`video_count`/
  `skipped_files` regardless of `complete`. There is no code branch that
  omits any of these fields while in progress; the "In Progress" sample is
  simply an incomplete excerpt, not a distinct schema. Per the project's
  `oneOf`-means-disjoint-branches convention, the spec models this as a
  single `MultimediaUploadStatus` schema (all fields always required), not
  a `oneOf` -- the two would not be disjoint (every "in progress" value also
  satisfies the "complete" branch's required-field list, just with
  placeholder values), which is exactly the "using `oneOf` to express
  uncertainty" anti-pattern the conventions warn against.
- **`getMultimediaUploadStatus` genuinely has a 404 and a 500 with real JSON
  bodies**, unlike `getFixtureUploadStatus` (documented in `fixture.yaml`
  as always-200). `_handle_multimedia_status`
  (`app_import_api.py:138-163`) explicitly returns
  `JsonResponse({'success': False, 'error': ...}, status=404)` for a
  missing app or an unknown/expired `processing_id`
  (`ResourceNotFound`/`BulkMultimediaStatusCache.get() is None`,
  `:140-159`), and `JsonResponse(..., status=500)` when
  `get_download_context` raises `TaskFailedError` (`:146-152`). The 500
  path requires a Celery worker to actually process and fail the task to
  exercise; not verified by the offline checks run for this task.
- **`bulkUploadCases` has no throttle at all, unlike every comparable
  upload endpoint in this API.** `corehq/apps/case_importer/views.py` never
  imports or applies `api_throttle`
  (`corehq/apps/api/decorators.py:51-61`) on `bulk_case_upload_api`
  (`views.py:461-467`), unlike `import_app_api`/`upload_multimedia_api`/
  `multimedia_status_api` (`app_import_api.py:31,86,132`, each decorated
  with `@api_throttle`) and `FixtureResource`'s tastypie-level `HQThrottle`.
  The spec omits a `429` response for `bulkUploadCases`, with an inline
  comment explaining why, rather than documenting one the code cannot
  produce.
- **`bulk_case_upload_api`'s failure response really does use HTTP 500 as
  its transport status, matching its own body's `code: 500`** -- worth
  flagging because several other upload endpoints in this API (documented
  in `fixture.yaml`) return `code`/outcome fields that diverge from an
  always-200 transport status. Here `json_response(..., status_code=500)`
  (`views.py:482`) genuinely sets the HTTP status to match.
- **A file/`case_type`-missing request is a `code: 500`, not a `400`, and
  `bulk-upload-cases.rst` does not claim otherwise.** `_bulk_case_upload_api`
  (`views.py:486-493`) raises `ImporterError` for a missing `file` or
  `case_type`, which the outer `bulk_case_upload_api` catches and turns into
  the same `code: 500` JSON body as any other importer error
  (`views.py:474-482`). Not a discrepancy (the reST page's response table,
  `:91-99`, only ever documents `200`/`500`), but easy to assume a REST API
  would use `400` for a missing required parameter -- it does not, here.
