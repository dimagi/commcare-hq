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
    upsert_base = _strip_internal_fields(
        jsonobject_to_schema(JsonCaseUpsert),
        ('case_id', 'user_id', 'is_new_case'),
    )
    upsert_item = _with_create_flag(
        upsert_base,
        {'type': 'boolean', 'nullable': True, 'enum': [None]},
        'Upserts a case by external_id: updates it if a case with that '
        'external_id already exists, or creates it otherwise.',
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
_POST_SINGLE_SCHEMA = _strip_internal_fields(
    jsonobject_to_schema(JsonCaseCreation),
    ('case_id', 'user_id', 'is_new_case'),
)

# user_id and is_new_case are excluded for the same reasons as above.
_PUT_SINGLE_SCHEMA = _strip_internal_fields(
    jsonobject_to_schema(JsonCaseUpdate),
    ('user_id', 'is_new_case'),
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
        'case-update branch applies (neither is required).'
    ),
    'anyOf': [_POST_SINGLE_SCHEMA, _PUT_SINGLE_SCHEMA],
}

_BULK_FETCH_SCHEMA = {
    'type': 'object',
    'properties': {
        'case_ids': {'type': 'array', 'items': {'type': 'string'}},
        'external_ids': {'type': 'array', 'items': {'type': 'string'}},
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
        'domain': {'type': 'string'},
        'case_id': {'type': 'string'},
        'case_type': {'type': 'string'},
        'case_name': {'type': 'string'},
        'external_id': {'type': 'string', 'nullable': True},
        'owner_id': {'type': 'string'},
        'date_opened': {'type': 'string', 'format': 'date-time'},
        'last_modified': {'type': 'string', 'format': 'date-time'},
        'server_last_modified': {'type': 'string', 'format': 'date-time'},
        'indexed_on': {'type': 'string', 'format': 'date-time'},
        'closed': {'type': 'boolean'},
        'date_closed': {
            'type': 'string',
            'format': 'date-time',
            'nullable': True,
        },
        'properties': {
            'type': 'object',
            'additionalProperties': {'type': 'string'},
        },
        'indices': {
            'type': 'object',
            'additionalProperties': {
                'type': 'object',
                'properties': {
                    'case_id': {'type': 'string'},
                    'case_type': {'type': 'string'},
                    'relationship': {'type': 'string'},
                },
            },
        },
    },
}

# ``get_bulk()``/``get_list()`` include an error stub, not a case, for
# any ID that couldn't be resolved (not found, wrong domain, or no
# permission) -- see their docstrings/callers in get_bulk.py and
# get_list.py.
_CASE_OR_ERROR_SCHEMA = {
    'anyOf': [_CASE_SCHEMA, {'type': 'object', 'properties': {
        'error': {'type': 'string'},
    }}],
}

_LIST_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'matching_records': {'type': 'integer'},
        'cases': {'type': 'array', 'items': _CASE_OR_ERROR_SCHEMA},
        'next': {
            'type': 'object',
            'description': 'Present only when more records match than '
                          'were returned; pass its "cursor" value back '
                          'as a query parameter to fetch the next page.',
            'properties': {'cursor': {'type': 'string'}},
        },
    },
    'required': ['matching_records', 'cases'],
}

_BULK_FETCH_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'cases': {'type': 'array', 'items': _CASE_OR_ERROR_SCHEMA},
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
        'form_id': {'type': 'string'},
        'case': _CASE_SCHEMA,
    },
    'required': ['form_id', 'case'],
}

_BULK_UPDATE_RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'form_id': {'type': 'string'},
        'cases': {'type': 'array', 'items': _CASE_SCHEMA},
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
        'case. POST with a list performs a bulk change: each item '
        'creates or updates a case according to its own "create" field, '
        'or is upserted by external_id when "create" is omitted. PUT to '
        'the case ID or external ID in the URL updates that case; PUT '
        'to the external ID URL is a genuine upsert, creating the case '
        'if none exists with that external ID. PUT to the list URL '
        '(no ID in the path) instead identifies the case via a '
        'case_id/external_id field in the body, and requires the case '
        'to already exist -- it is not an upsert.'
    ),
    'paths': [CASE_LIST_PATH, CASE_DETAIL_PATH, CASE_EXT_PATH],
    'methods': ['get', 'post', 'put'],
    'parameters': filter_parameters(),
    'path_parameter_descriptions': {
        'case_id': (
            'The case ID. For GET, multiple IDs may be given as a '
            'comma-separated list, e.g. "id1,id2,id3", to fetch several '
            'cases at once.'
        ),
        'external_id': "The case's external ID.",
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
