"""OpenAPI declarations for the Case API v2 views.

Kept out of ``hqcase/views.py`` so that a request-handling module is not
majority documentation data. ``views.py`` imports only the two kwargs
bundles at the bottom of this module.

``_CASE_SCHEMA`` is transcribed by hand from ``serialize_case()``, which is
itself a dict literal with no schema to derive from -- unlike every other
documented API, whose response schema is derived from tastypie's metadata.
``TestCaseApiSchemaMatchesItsSerializer`` is what keeps the two from
drifting: it pins the key sets in both directions against a real serialized
case. Add a field here and it fails until the serializer has it too, and
vice versa.
"""
from corehq.apps.api.const import (
    CASE_BULK_FETCH_PATH,
    CASE_DETAIL_PATH,
    CASE_EXT_PATH,
    CASE_LIST_PATH,
)
from corehq.apps.api.openapi.jsonobject_schema import jsonobject_to_schema
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE

from .openapi_parameters import filter_parameters
from .updates import JsonCaseCreation, JsonCaseUpdate, JsonCaseUpsert


def _strip_internal_fields(schema, fields):
    """Drop properties a client never actually controls.

    ``jsonobject_to_schema()`` surfaces every property of the underlying
    model generically; the fields named here are real properties of that
    model, but not real request fields for this API -- see the callers
    below for exactly why each one is excluded.
    """
    schema = dict(schema)
    schema['properties'] = dict(schema['properties'])
    required = list(schema.get('required', []))
    for field in fields:
        schema['properties'].pop(field, None)
        if field in required:
            required.remove(field)
    if required:
        schema['required'] = required
    else:
        schema.pop('required', None)
    return schema


def _with_create_flag(schema, create_property, description):
    """A copy of ``schema`` with a required, wire-only ``create`` field.

    ``create`` is popped from the payload by ``_get_bulk_updates()``
    before a jsonobject is ever built (see ``updates.py``), so it has no
    corresponding jsonobject property and ``jsonobject_to_schema()``
    never produces it -- it has to be added by hand for every bulk item
    variant.
    """
    schema = dict(schema)
    schema['description'] = description
    schema['properties'] = {**schema['properties'], 'create': create_property}
    schema['required'] = ['create', *schema.get('required', [])]
    return schema


def _describe(schema, descriptions):
    """A copy of ``schema`` with a ``description`` merged into each of its
    top-level properties named in ``descriptions``.

    ``jsonobject_to_schema()`` produces bare type schemas with no prose --
    this lets one dictionary of English text live next to the jsonobject
    model it describes, rather than threading it through
    ``_property_schema()``. Keys in ``descriptions`` that name a property
    the schema doesn't have (e.g. because ``_strip_internal_fields()``
    removed it, or the model doesn't declare it) are silently ignored, so
    one shared dictionary can be reused across the create/update/upsert
    variants without each needing its own subset.
    """
    schema = dict(schema)
    properties = dict(schema['properties'])
    for key, text in descriptions.items():
        if key in properties:
            properties[key] = {**properties[key], 'description': text}
    schema['properties'] = properties
    return schema


def _describe_nested(schema, prop_name, descriptions):
    """Like ``_describe()``, but merges into the ``additionalProperties``
    schema of ``prop_name`` -- i.e. a ``DictProperty`` of nested objects,
    such as ``indices``.
    """
    schema = dict(schema)
    properties = dict(schema['properties'])
    nested = properties[prop_name]
    properties[prop_name] = {
        **nested,
        'additionalProperties': _describe(
            nested['additionalProperties'], descriptions
        ),
    }
    schema['properties'] = properties
    return schema


# Shared across JsonCaseCreation, JsonCaseUpdate and JsonCaseUpsert: each
# strips a different subset of these via _strip_internal_fields(), so a
# key naming a field one of them doesn't have is simply unused for that
# schema (see _describe()).
_FIELD_DESCRIPTIONS = {
    # The runtime check is JsonCaseUpdate.validate(); the published
    # wording states the effect rather than naming it, since a caller
    # cannot look the class up.
    'case_id': (
        'The ID of the case to update. Required to identify the case '
        'unless external_id is given instead -- a request with neither '
        'is rejected, even though this schema cannot express that. Not '
        'used when creating a case, where the ID is always '
        'server-generated.'
    ),
    'case_name': (
        "The case's display name. Required when creating a case; "
        'optional on updates and upserts, where omitting it leaves the '
        'existing name unchanged. Maximum length 255 characters.'
    ),
    'case_type': (
        'The case type, as defined by the project\'s data model. '
        'Required when creating a case; optional on updates and '
        'upserts, where omitting it leaves the existing type unchanged. '
        'Maximum length 255 characters.'
    ),
    'owner_id': (
        "The ID of the case's new owner: a user, case-sharing group, or "
        'location ID. Not validated against a real owner beyond the '
        'access checks enforced for the authenticated user. Required '
        'when creating a case; optional on updates and upserts, where '
        'omitting it leaves the current owner unchanged. Maximum length '
        '255 characters.'
    ),
    'external_id': (
        'An external identifier for the case, e.g. from another system. '
        'Maximum length 255 characters.'
    ),
    'temporary_id': (
        'An identifier for this case, unique within the current bulk '
        'request, that another item in the same request can reference '
        'from an index instead of a real case_id -- see '
        '"indices.<name>.temporary_id". Not stored; discarded once the '
        'request has been processed.'
    ),
    'properties': (
        'User-defined case properties to set, as name/value pairs. All '
        'values must be strings. Property names must be valid XML '
        'element names (non-blank, not starting with a digit or with '
        '"xml") and may not be case_type, case_name or owner_id, which '
        'are set via their own top-level fields instead.'
    ),
    'indices': (
        "The case's indices (relationships to other cases) to set, "
        'keyed by an identifier of your choosing (e.g. "parent", '
        '"host"), which must also be a valid XML element name as '
        'described for properties above.'
    ),
    'close': 'Set to true to close the case as part of this update. '
             'Defaults to false.',
}

# JsonIndex fields, nested under indices.<name> on every create/update/
# upsert schema.
_INDEX_DESCRIPTIONS = {
    'case_id': 'The ID of the related case. Exactly one of case_id, '
               'external_id or temporary_id must be given.',
    'external_id': 'The external ID of the related case. Exactly one of '
                   'case_id, external_id or temporary_id must be given.',
    'temporary_id': 'The temporary_id of another case being created or '
                    'updated in the same bulk request. Exactly one of '
                    'case_id, external_id or temporary_id must be given.',
    'case_type': "The related case's case type. Required whenever "
                 'case_id, external_id or temporary_id is given.',
    'relationship': (
        '"child" or "extension" (see the Extension Cases feature). '
        'Required whenever case_id, external_id or temporary_id is '
        'given.'
    ),
}


def _case_write_schema(model, internal_fields):
    """The published request schema for one of the case write models.

    ``jsonobject_to_schema()`` produces a bare, generic schema. Turning
    one into published documentation takes the same three steps every
    time -- drop the properties a client does not control, hang prose on
    the top-level properties, and hang it on the nested index objects --
    so the model and the fields it excludes are all that differ between
    the create, update and upsert variants. Each caller says why its own
    exclusions are not real request fields.
    """
    return _describe_nested(
        _describe(
            _strip_internal_fields(
                jsonobject_to_schema(model), internal_fields
            ),
            _FIELD_DESCRIPTIONS,
        ),
        'indices',
        _INDEX_DESCRIPTIONS,
    )


def _bulk_item_schema():
    """The schema for one item of a bulk (list-body) create/update.

    ``_get_bulk_updates()`` requires every item to carry a ``create``
    field and dispatches on its value: ``true`` builds a
    ``JsonCaseCreation``, ``false`` a ``JsonCaseUpdate``, and ``null`` a
    ``JsonCaseUpsert`` (``updates.py:239-258``). These three branches
    have different required fields, so a single flat schema (e.g. just
    reusing the single-object creation schema) cannot represent a bulk
    item honestly -- it would wrongly require creation-only fields on
    update/upsert items, and never mention ``create`` at all.
    """
    create_item = _with_create_flag(
        _POST_SINGLE_SCHEMA,
        {'type': 'boolean', 'enum': [True]},
        'Creates a new case. Requires case_name, case_type and '
        'owner_id, like a single-object POST.',
    )
    update_item = _with_create_flag(
        _PUT_SINGLE_SCHEMA,
        {'type': 'boolean', 'enum': [False]},
        'Updates an existing case. Must include either "case_id" or '
        '"external_id" to identify the case. Neither is individually '
        'required by this schema, because either one satisfies the '
        'requirement; a request carrying neither is rejected.',
    )
    # Unlike the ext-ID PUT endpoint, there is no URL to supply
    # external_id from here, so it is genuinely required in the body.
    upsert_base = _case_write_schema(
        JsonCaseUpsert, ('case_id', 'user_id', 'is_new_case')
    )
    upsert_item = _with_create_flag(
        upsert_base,
        {'type': 'boolean', 'nullable': True, 'enum': [None]},
        'Upserts a case by external_id: updates it if a case with that '
        'external_id already exists, or creates it otherwise. CommCare '
        'HQ looks up every upserted item\'s external_id before any of '
        'them are saved, so if this same external_id appears more than '
        'once in one request, every occurrence after the first is '
        'treated as "not found yet" and a duplicate case is created for '
        'it -- keep external_ids unique within a single request. The '
        'same race exists across concurrent requests: two requests '
        'upserting the same external_id at the same time can each '
        'create a case.',
    )
    return {'oneOf': [create_item, update_item, upsert_item]}


def _single_or_bulk_schema(single_schema):
    """A schema accepting either one object, or a list of bulk items.

    The list branch is capped at CASEBLOCK_CHUNKSIZE: see
    ``_get_bulk_updates()``'s own check in ``updates.py``, which rejects
    a bigger list outright with "You cannot submit more than 100
    updates in a single request".
    """
    return {
        'oneOf': [
            single_schema,
            {
                'type': 'array',
                'items': _bulk_item_schema(),
                'maxItems': CASEBLOCK_CHUNKSIZE,
                'description': (
                    'Performs a bulk create/update: each item is created, '
                    'updated or upserted according to its own "create" '
                    'field. All items are submitted in a single form. '
                    f'Capped at {CASEBLOCK_CHUNKSIZE} items per request; a '
                    'longer list is rejected in full, with no cases '
                    'changed, with the message "You cannot submit more '
                    f'than {CASEBLOCK_CHUNKSIZE} updates in a single '
                    'request".'
                ),
            },
        ]
    }


# case_id (rejected by JsonCaseCreation.wrap() -- the ID is always
# server-generated for a creation), user_id (overwritten unconditionally
# with the authenticated user's ID in updates._get_individual_update(),
# so a client-supplied value is always discarded), and is_new_case (not a
# real request field at all -- it only appears because jsonobject treats
# the plain `is_new_case = True` class attribute as a boolean property)
# are excluded so the published schema documents only what a client
# actually controls.
_POST_SINGLE_SCHEMA = _case_write_schema(
    JsonCaseCreation, ('case_id', 'user_id', 'is_new_case')
)

# user_id and is_new_case are excluded for the same reasons as above.
_PUT_SINGLE_SCHEMA = _case_write_schema(
    JsonCaseUpdate, ('user_id', 'is_new_case')
)
# A single-object PUT to the list path has no case ID from the URL, so
# JsonCaseUpdate.validate()'s requirement -- case_id or external_id --
# is a real, enforced constraint on the body. On the detail path
# (case_id in the URL), _handle_case_put_post() injects case_id into the
# body automatically, so that constraint is already satisfied and would
# be misleading to publish there.
_PUT_LIST_SINGLE_SCHEMA = {
    **_PUT_SINGLE_SCHEMA,
    'anyOf': [{'required': ['case_id']}, {'required': ['external_id']}],
}

# The runtime never actually builds a JsonCaseUpsert for this endpoint:
# _handle_ext_put() looks the case up first, then picks JsonCaseCreation
# (case absent) or JsonCaseUpdate (case present). Those two have
# different required fields (creation requires case_name/case_type/
# owner_id; update doesn't), so publishing one flat "optional
# everything" schema -- as a previous revision of this file did --
# accepted payloads the API would reject with a 400 when the case
# doesn't exist.
#
# This must be anyOf, not oneOf: the client cannot know in advance
# whether the case exists, so either shape is an acceptable thing to
# send. A creation payload (case_name/case_type/owner_id all present)
# legitimately satisfies *both* branches -- nothing forbids an update
# payload from also having those fields -- so oneOf's "exactly one
# branch matches" rule would wrongly reject it. anyOf's "at least one
# branch matches" is the real contract.
_PUT_EXT_SCHEMA = {
    'description': (
        'Upsert by external ID. If no case with this external ID '
        'exists, the case-creation branch applies (case_name, '
        'case_type and owner_id are required); if one does, the '
        'case-update branch applies (neither is required). Two '
        'requests upserting the same external ID at the same time can '
        'race: both may see no existing case and each create one.'
    ),
    'anyOf': [_POST_SINGLE_SCHEMA, _PUT_SINGLE_SCHEMA],
}

_BULK_FETCH_SCHEMA = {
    'type': 'object',
    'properties': {
        'case_ids': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': 'Case IDs to fetch.',
        },
        'external_ids': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': 'External IDs to fetch.',
        },
    },
    'anyOf': [
        {'required': ['case_ids']},
        {'required': ['external_ids']},
    ],
}

# Read from ``core.serialize_case()``/``serialize_es_case()``, which are
# the two functions that actually build a case dict for this API --
# GET, bulk-fetch and the create/update responses below all go through
# one or the other. ``properties`` and ``indices`` are declared as
# generic string-keyed maps because their keys are project-defined case
# properties and index identifiers, not fixed field names. Nothing here
# is marked ``required``: ``get_fields_filter_fn`` (the ``properties=``
# query parameter) can drop any subset of these keys from the actual
# response.
_CASE_SCHEMA = {
    'type': 'object',
    'properties': {
        'domain': {
            'type': 'string',
            'description': "The domain (project space) the case belongs "
                           'to.',
        },
        'case_id': {
            'type': 'string',
            'description': "The case's unique, server-generated ID.",
        },
        'case_type': {
            'type': 'string',
            'description': "The case type, as defined by the project's "
                           'data model.',
        },
        'case_name': {
            'type': 'string',
            'description': "The case's display name.",
        },
        'external_id': {
            'type': 'string',
            'nullable': True,
            'description': 'An external identifier for the case, e.g. '
                           'from another system. Null if none was set.',
        },
        'owner_id': {
            'type': 'string',
            'description': "The ID of the case's current owner: a "
                           'user, case-sharing group, or location ID.',
        },
        'date_opened': {
            'type': 'string',
            'format': 'date-time',
            'description': 'The date and time the case was created.',
        },
        'last_modified': {
            'type': 'string',
            'format': 'date-time',
            'description': "The date and time of the case's last "
                           'update, as recorded by the client that '
                           'submitted it. Compare with '
                           'server_last_modified (the server\'s own '
                           'record of when it received that update) and '
                           'indexed_on (when the case was last written '
                           'to the search index this API reads from) -- '
                           'the three can differ, e.g. when a '
                           "client's clock is skewed, or the search "
                           'index has fallen behind.',
        },
        'server_last_modified': {
            'type': 'string',
            'format': 'date-time',
            'description': "The date and time the server processed the "
                           "case's last update. See last_modified for "
                           'how this differs from that field and from '
                           'indexed_on.',
        },
        'indexed_on': {
            'type': 'string',
            'format': 'date-time',
            'description': 'The date and time the case was last written '
                           'to the search index this API reads from, '
                           'used to paginate list results; it can lag '
                           'slightly behind server_last_modified. When '
                           'this case is returned directly from a '
                           'create/update response (as opposed to a '
                           'GET), the case has not yet reached the '
                           'search index, so this is instead the time '
                           'the response was generated. See '
                           'last_modified for how these three timestamps '
                           'differ.',
        },
        'closed': {
            'type': 'boolean',
            'description': 'Whether the case is closed. Send '
                           '"close": true to close a case. This API '
                           'cannot reopen one: a case is reopened by '
                           'archiving the form that closed it, which is '
                           'done in CommCare HQ rather than here.',
        },
        'date_closed': {
            'type': 'string',
            'format': 'date-time',
            'nullable': True,
            'description': 'The date and time the case was closed. '
                           'Null while the case is open, and null again '
                           'if the case is later reopened by archiving '
                           'the form that closed it.',
        },
        'properties': {
            'type': 'object',
            'additionalProperties': {'type': 'string'},
            'description': "The case's user-defined properties, each a "
                           'string value keyed by property name.',
        },
        'indices': {
            'type': 'object',
            'additionalProperties': {
                'type': 'object',
                'properties': {
                    'case_id': {
                        'type': 'string',
                        'description': 'The ID of the related (target) '
                                       'case.',
                    },
                    'case_type': {
                        'type': 'string',
                        'description': "The related case's case type.",
                    },
                    'relationship': {
                        'type': 'string',
                        'description': '"child" or "extension".',
                    },
                },
            },
            'description': "The case's indices (relationships to other "
                           'cases), keyed by index identifier (e.g. '
                           '"parent", "host").',
        },
    },
}

# ``get_bulk()``/``get_list()`` include an error stub, not a case, for
# any ID that couldn't be resolved (not found, wrong domain, or no
# permission) -- see their docstrings/callers in get_bulk.py and
# get_list.py. ``_get_error_doc()`` in get_bulk.py also includes the
# case_id or external_id that couldn't be resolved alongside "error";
# the single-case detail endpoints (``_get_single_case()``,
# ``_handle_ext_get()``) never include one, since there is only ever
# one ID to have failed to resolve.
_CASE_OR_ERROR_SCHEMA = {
    'anyOf': [_CASE_SCHEMA, {'type': 'object', 'properties': {
        'error': {
            'type': 'string',
            'description': 'Present instead of a case when it could '
                           "not be resolved: it doesn't exist, belongs "
                           'to a different domain, or the caller lacks '
                           'permission to see it. In a bulk result '
                           '(bulk-fetch, or a comma-separated case_id '
                           'list) this is always the literal text "not '
                           'found", even when the actual cause is a '
                           'domain mismatch or a permission error; the '
                           'single-case detail endpoints give a more '
                           'specific message instead.',
        },
        'case_id': {
            'type': 'string',
            'description': 'The case_id that could not be resolved. '
                           'Present only in a bulk result.',
        },
        'external_id': {
            'type': 'string',
            'description': 'The external_id that could not be '
                           'resolved. Present only in a bulk result.',
        },
    }}],
}

_LIST_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'matching_records': {
            'type': 'integer',
            'description': "The total number of cases matching this "
                           "request's filters, not the number of cases "
                           'in this page\'s "cases" array -- check for '
                           '"next" to determine whether more pages '
                           'remain.',
        },
        'cases': {
            'type': 'array',
            'items': _CASE_OR_ERROR_SCHEMA,
            'description': 'The page of matching cases, each serialized '
                           'as described above.',
        },
        'next': {
            'type': 'object',
            'description': 'Present only when more records match than '
                          'were returned; pass its "cursor" value back '
                          'as a query parameter to fetch the next page.',
            'properties': {
                'cursor': {
                    'type': 'string',
                    'description': 'Opaque pagination state; pass back '
                                   'as the "cursor" query parameter.',
                },
            },
        },
    },
    'required': ['matching_records', 'cases'],
}

# get_bulk() returns matching_records/missing_records alongside cases
# (see BulkFetchResults in get_bulk.py, and _handle_bulk_fetch() /
# _get_bulk_cases() in this module, which pass its dict straight
# through to JsonResponse()) -- they belong on this schema too, not
# just on cases.
_BULK_FETCH_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'matching_records': {
            'type': 'integer',
            'description': 'The number of requested case_ids/'
                           'external_ids that were found. Unlike the '
                           'list endpoint\'s "matching_records", this '
                           "isn't counting matches against a filter -- "
                           'bulk-fetch takes explicit IDs, so this is '
                           'simply the count of IDs that resolved.',
        },
        'missing_records': {
            'type': 'integer',
            'description': 'The number of requested case_ids/'
                           'external_ids that could not be found.',
        },
        'cases': {
            'type': 'array',
            'items': _CASE_OR_ERROR_SCHEMA,
            'description': 'The requested cases, one entry per case_id/'
                           'external_id given, in the same order '
                           '(case_ids first, then external_ids, if '
                           'both were supplied). A case that could not '
                           'be found appears as an error stub instead.',
        },
    },
    'required': ['cases'],
}

# handle_case_update() returns one case for a single create/update, or a
# list for a bulk one (see its ``is_bulk`` branch) -- so the create/
# update endpoints' response is genuinely one shape or the other, not a
# single fixed schema.
_UPDATE_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'form_id': {
            'type': 'string',
            'description': 'The ID of the form generated to submit this '
                           'change.',
        },
        'case': {
            **_CASE_SCHEMA,
            'description': "The case's state after applying this "
                           'create/update.',
        },
    },
    'required': ['form_id', 'case'],
}

_BULK_UPDATE_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'form_id': {
            'type': 'string',
            'description': 'The ID of the single form generated to '
                           'submit every case in this bulk request.',
        },
        'cases': {
            'type': 'array',
            'items': _CASE_SCHEMA,
            'description': 'The state of each case after applying this '
                           'bulk create/update, in the same order as '
                           'the request.',
        },
    },
    'required': ['form_id', 'cases'],
}

_SINGLE_OR_BULK_UPDATE_RESPONSE_SCHEMA = {
    'anyOf': [_UPDATE_RESPONSE_SCHEMA, _BULK_UPDATE_RESPONSE_SCHEMA],
}


CASE_API_DOCS = {
    'summary': 'Cases',
    'description': (
        'Fetch, create and update cases. GET returns a page of cases '
        'matching the given filters, or a single case when a case ID is '
        'given. POST with a single JSON object always creates a new '
        'case -- it does not check external_id for an existing match, '
        'so posting one that already exists creates a second case with '
        'a duplicate external_id; use PUT by external ID instead if '
        'that is not what you want. POST with a list performs a bulk '
        'change: each item creates or updates a case according to its '
        'own "create" field, or is upserted by external_id when '
        '"create" is omitted. PUT to the case ID or external ID in the '
        'URL updates that case; PUT to the external ID URL is a '
        'genuine upsert, creating the case if none exists with that '
        'external ID. PUT to the list URL (no ID in the path) instead '
        'identifies the case via a case_id/external_id field in the '
        'body, and requires the case to already exist -- it is not an '
        'upsert. Every change is attributed to the authenticated '
        'caller; there is no way to submit a change as another user. '
        'A change can also fail only once the form built from it is '
        'processed, rather than during upfront validation; in that '
        'case no case changes are made and the response is a 400 with '
        '"error" and "form_id" fields (the ID of the resulting error '
        'form), rather than the "error"-only shape used for other '
        'input errors.'
    ),
    'paths': [CASE_LIST_PATH, CASE_DETAIL_PATH, CASE_EXT_PATH],
    'methods': ['get', 'post', 'put'],
    'parameters': filter_parameters(),
    'path_parameter_descriptions': {
        'case_id': (
            'The case ID. For GET, multiple IDs may be given as a '
            'comma-separated list, e.g. "id1,id2,id3", to fetch several '
            'cases at once -- for more than around 100 IDs, prefer '
            'POST /bulk-fetch/, which has no such practical limit. For '
            'PUT, if the request body also includes a "case_id" field, '
            'the body\'s value is used to identify the case, and this '
            'path value is only used to fill it in when the body omits '
            'it; the two are not checked against each other.'
        ),
        'external_id': (
            "The case's external ID. If more than one case in the "
            "domain shares this external ID, GET fails with a 400 "
            'listing every matching case_id, rather than returning any '
            'one of them.'
        ),
    },
    # 'post' and 'put' (no path) are the single-object schemas, so that
    # introspecting `case_api._openapi_docs.request_schemas['post']`
    # (see test_case_v2_docs.py) finds a plain object schema; only the
    # list path actually needs -- and gets, via the path-specific
    # override -- the bulk (single-or-list) version.
    'request_schemas': {
        'post': _POST_SINGLE_SCHEMA,
        (CASE_LIST_PATH, 'post'): _single_or_bulk_schema(_POST_SINGLE_SCHEMA),
        (CASE_LIST_PATH, 'put'): _single_or_bulk_schema(
            _PUT_LIST_SINGLE_SCHEMA
        ),
        (CASE_DETAIL_PATH, 'put'): _PUT_SINGLE_SCHEMA,
        (CASE_EXT_PATH, 'put'): _PUT_EXT_SCHEMA,
    },
    'examples': {
        'post_request': 'case/v2/post_request.json',
        'put_request': 'case/v2/put_request.json',
        (CASE_EXT_PATH, 'put_request'): 'case/v2/put_ext_request.json',
        (CASE_LIST_PATH, 'post_request'): 'case/v2/bulk_post_request.json',
    },
    # 'get'/'post'/'put' (no path) are the single-case shapes, for the
    # same introspection reason as request_schemas above; the list
    # path's GET returns the paginated envelope, and its POST/PUT
    # return either the single- or bulk-update shape depending on
    # whether the request body was an object or a list (see
    # handle_case_update()'s ``is_bulk`` branch).
    'response_schemas': {
        'get': _CASE_SCHEMA,
        (CASE_LIST_PATH, 'get'): _LIST_RESPONSE_SCHEMA,
        # A comma-separated case_id list on the detail path returns the
        # bulk-fetch shape instead of a single case -- see
        # ``_handle_get()``.
        (CASE_DETAIL_PATH, 'get'): {
            'anyOf': [_CASE_SCHEMA, _BULK_FETCH_RESPONSE_SCHEMA],
        },
        'post': _UPDATE_RESPONSE_SCHEMA,
        (CASE_LIST_PATH, 'post'): _SINGLE_OR_BULK_UPDATE_RESPONSE_SCHEMA,
        'put': _UPDATE_RESPONSE_SCHEMA,
        (CASE_LIST_PATH, 'put'): _SINGLE_OR_BULK_UPDATE_RESPONSE_SCHEMA,
    },
}

CASE_BULK_FETCH_DOCS = {
    'summary': 'Bulk fetch cases',
    'description': (
        'Fetch multiple cases by case ID and/or external ID in a single '
        'request. The body must include "case_ids" and/or '
        '"external_ids" (both may be given together). Unlike '
        'GET /a/{domain}/api/case/v2/<case_id>,<case_id>,..., this has '
        'no practical limit on how many cases can be requested at once.'
    ),
    'paths': [CASE_BULK_FETCH_PATH],
    'methods': ['post'],
    'request_schemas': {'post': _BULK_FETCH_SCHEMA},
    'response_schemas': {'post': _BULK_FETCH_RESPONSE_SCHEMA},
    'examples': {'post_request': 'case/v2/bulk_fetch_request.json'},
}
