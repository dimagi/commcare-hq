import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied

from soil import DownloadBase

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import allow_cors, api_throttle
from corehq.apps.domain.decorators import (
    api_auth,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.hqwebapp.decorators import waf_allow, use_bootstrap5
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.util.es.elasticsearch import NotFoundError
from corehq.util.view_utils import reverse
from corehq.apps.locations.permissions import user_can_access_case
from corehq.apps.locations.permissions import location_safe
from corehq.form_processor.models import CommCareCase

from corehq.apps.api.openapi.jsonobject_schema import jsonobject_to_schema
from corehq.apps.api.openapi.view_adapter import api_docs

from .api.core import SubmissionError, UserError, serialize_case, serialize_es_case
from .api.field_filters import get_fields_filter_fn
from .api.get_list import filter_parameters, get_list
from .api.get_bulk import get_bulk
from .api.updates import (
    JsonCaseCreation,
    JsonCaseUpdate,
    JsonCaseUpsert,
    handle_case_update,
)
from .tasks import delete_exploded_case_task, explode_case_task


class ExplodeCasesView(BaseProjectSettingsView, TemplateView):
    url_name = "explode_cases"
    template_name = "hqcase/explode_cases.html"
    page_title = "Explode Cases"

    @method_decorator(use_bootstrap5)
    @method_decorator(require_superuser_or_contractor)
    def dispatch(self, *args, **kwargs):
        return super(ExplodeCasesView, self).dispatch(*args, **kwargs)

    def get(self, request, domain):
        return super(ExplodeCasesView, self).get(request, domain)

    def get_context_data(self, **kwargs):
        context = super(ExplodeCasesView, self).get_context_data(**kwargs)
        context.update({
            'domain': self.domain,
        })
        return context

    def post(self, request, domain):
        if 'explosion_id' in request.POST:
            return self.delete_cases(request, domain)
        else:
            return self.explode_cases(request, domain)

    def explode_cases(self, request, domain):
        user_id = request.POST.get('user_id')
        factor = request.POST.get('factor', '2')
        try:
            factor = int(factor)
        except ValueError:
            messages.error(request, 'factor must be an int; was: %s' % factor)
        else:
            download = DownloadBase()
            res = explode_case_task.delay(self.domain, user_id, factor)
            download.set_task(res)

            return redirect('hq_soil_download', self.domain, download.download_id)

    def delete_cases(self, request, domain):
        explosion_id = request.POST.get('explosion_id')
        download = DownloadBase()
        res = delete_exploded_case_task.delay(self.domain, explosion_id)
        download.set_task(res)
        return redirect('hq_soil_download', self.domain, download.download_id)


CASE_LIST_PATH = '/a/{domain}/api/case/v2/'
CASE_DETAIL_PATH = '/a/{domain}/api/case/v2/{case_id}/'
CASE_EXT_PATH = '/a/{domain}/api/case/v2/ext/{external_id}/'
CASE_BULK_FETCH_PATH = '/a/{domain}/api/case/v2/bulk-fetch/'


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
    'case_id': (
        'The ID of the case to update. Required to identify the case '
        'unless external_id is given instead (JsonCaseUpdate.validate() '
        'enforces this at runtime -- see the request schema description '
        'above for exactly where). Not used when creating a case, where '
        'the ID is always server-generated.'
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
        '"external_id" to identify the case (JsonCaseUpdate.validate() '
        'enforces this at runtime, though neither is individually '
        'required by this schema, since either satisfies it).',
    )
    # Unlike the ext-ID PUT endpoint, there is no URL to supply
    # external_id from here, so it is genuinely required in the body.
    upsert_base = _describe_nested(
        _describe(
            _strip_internal_fields(
                jsonobject_to_schema(JsonCaseUpsert),
                ('case_id', 'user_id', 'is_new_case'),
            ),
            _FIELD_DESCRIPTIONS,
        ),
        'indices',
        _INDEX_DESCRIPTIONS,
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

    The list branch is capped at CASEBLOCK_CHUNKSIZE (100): see
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
                'maxItems': 100,
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
_POST_SINGLE_SCHEMA = _describe_nested(
    _describe(
        _strip_internal_fields(
            jsonobject_to_schema(JsonCaseCreation),
            ('case_id', 'user_id', 'is_new_case'),
        ),
        _FIELD_DESCRIPTIONS,
    ),
    'indices',
    _INDEX_DESCRIPTIONS,
)

# user_id and is_new_case are excluded for the same reasons as above.
_PUT_SINGLE_SCHEMA = _describe_nested(
    _describe(
        _strip_internal_fields(
            jsonobject_to_schema(JsonCaseUpdate),
            ('user_id', 'is_new_case'),
        ),
        _FIELD_DESCRIPTIONS,
    ),
    'indices',
    _INDEX_DESCRIPTIONS,
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
            'description': 'Whether the case is closed.',
        },
        'date_closed': {
            'type': 'string',
            'format': 'date-time',
            'nullable': True,
            'description': 'The date and time the case was closed. '
                           'Null while the case is open.',
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


@api_docs(
    summary='Cases',
    description=(
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
    doc_slug='case-v2',
    paths=[CASE_LIST_PATH, CASE_DETAIL_PATH, CASE_EXT_PATH],
    methods=['get', 'post', 'put'],
    parameters=filter_parameters(),
    path_parameter_descriptions={
        'case_id': (
            'The case ID. For GET, multiple IDs may be given as a '
            'comma-separated list, e.g. "id1,id2,id3", to fetch several '
            'cases at once.'
        ),
        'external_id': "The case's external ID.",
    },
    # 'post' and 'put' (no path) are the single-object schemas, so that
    # introspecting `case_api._openapi_docs.request_schemas['post']`
    # (see test_view_adapter.py) finds a plain object schema; only the
    # list path actually needs -- and gets, via the path-specific
    # override -- the bulk (single-or-list) version.
    request_schemas={
        'post': _POST_SINGLE_SCHEMA,
        (CASE_LIST_PATH, 'post'): _single_or_bulk_schema(_POST_SINGLE_SCHEMA),
        (CASE_LIST_PATH, 'put'): _single_or_bulk_schema(
            _PUT_LIST_SINGLE_SCHEMA
        ),
        (CASE_DETAIL_PATH, 'put'): _PUT_SINGLE_SCHEMA,
        (CASE_EXT_PATH, 'put'): _PUT_EXT_SCHEMA,
    },
    examples={
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
    response_schemas={
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
)
@waf_allow('XSS_BODY')
@csrf_exempt
@allow_cors(['OPTIONS', 'GET', 'POST', 'PUT'])
@api_auth(allow_creds_in_data=False)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@requires_privilege_with_fallback(privileges.API_ACCESS)
@api_throttle
@location_safe
def case_api(request, domain, case_id=None, external_id=None):
    try:
        if request.method == 'GET' and case_id:
            return _handle_get(request, case_id)
        if request.method == 'GET' and external_id:
            return _handle_ext_get(request, external_id)
        if request.method == 'GET' and not case_id:
            return _handle_list_view(request)
        if request.method == 'POST' and not case_id:
            return _handle_case_put_post(request, is_creation=True)
        if request.method == 'PUT' and external_id:
            return _handle_ext_put(request, external_id)
        if request.method == 'PUT':
            return _handle_case_put_post(request, is_creation=False, case_id=case_id)
        return JsonResponse({'error': "Request method not allowed"}, status=405)
    except UserError as e:
        return JsonResponse({'error': e.message}, status=400)


@api_docs(
    summary='Bulk fetch cases',
    description=(
        'Fetch multiple cases by case ID and/or external ID in a single '
        'request. The body must include "case_ids" and/or '
        '"external_ids" (both may be given together). Unlike '
        'GET /a/{domain}/api/case/v2/<case_id>,<case_id>,..., this has '
        'no practical limit on how many cases can be requested at once.'
    ),
    doc_slug='case-v2',
    paths=[CASE_BULK_FETCH_PATH],
    methods=['post'],
    request_schemas={'post': _BULK_FETCH_SCHEMA},
    response_schemas={'post': _BULK_FETCH_RESPONSE_SCHEMA},
    examples={'post_request': 'case/v2/bulk_fetch_request.json'},
)
@waf_allow('XSS_BODY')
@csrf_exempt
@allow_cors(['OPTIONS', 'GET', 'POST'])
@api_auth(allow_creds_in_data=False)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@requires_privilege_with_fallback(privileges.API_ACCESS)
@api_throttle
def case_api_bulk_fetch(request, domain):
    try:
        return _handle_bulk_fetch(request)
    except UserError as e:
        return JsonResponse({'error': e.message}, status=400)


def _handle_get(request, case_id):
    if ',' in case_id:
        return _get_bulk_cases(request, case_ids=case_id.split(','))
    return _get_single_case(request, case_id)


def _get_bulk_cases(request, case_ids=None, external_ids=None):
    res = get_bulk(request.domain, request.couch_user, case_ids, external_ids)
    filter_fields = get_fields_filter_fn(request.GET)
    res['cases'] = [
        filter_fields(case) if 'error' not in case else case
        for case in res['cases']
    ]
    return JsonResponse(res)


def _get_single_case(request, case_id):
    try:
        case = case_search_adapter.get(case_id)
        if case['domain'] != request.domain:
            raise NotFoundError()
        if not user_can_access_case(request.domain, request.couch_user, case, es_case=True):
            raise PermissionDenied()
    except NotFoundError:
        return JsonResponse({'error': f"Case '{case_id}' not found"}, status=404)
    except PermissionDenied:
        return JsonResponse({'error': f"Insufficient permission for Case '{case_id}'"}, status=403)
    filter_fields = get_fields_filter_fn(request.GET)
    return JsonResponse(filter_fields(serialize_es_case(case)))


def _handle_ext_get(request, external_id):
    case = _get_by_external_id(request.domain, external_id)
    if case is None:
        return JsonResponse(
            {'error': f"Case '{external_id}' not found"},
            status=404,
        )

    try:
        if case.domain != request.domain:
            raise NotFoundError()
        if not user_can_access_case(request.domain, request.couch_user, case):
            raise PermissionDenied()
    except NotFoundError:
        return JsonResponse(
            {'error': f"Case '{case.case_id}' not found"},
            status=404,
        )
    except PermissionDenied:
        return JsonResponse(
            {'error': f"Insufficient permission for Case '{case.case_id}'"},
            status=403,
        )
    filter_fields = get_fields_filter_fn(request.GET)
    return JsonResponse(filter_fields(serialize_case(case)))


def _get_by_external_id(domain, external_id):
    try:
        return CommCareCase.objects.get_case_by_external_id(
            domain,
            external_id,
            raise_multiple=True,
        )
    except CommCareCase.MultipleObjectsReturned as err:
        case_ids = [case.case_id for case in err.cases]
        raise UserError(
            f"Multiple cases found with external_id '{external_id}': "
            f"{', '.join(case_ids)}"
        )


def _handle_bulk_fetch(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UserError("Payload must be valid JSON")

    case_ids = data.get('case_ids')
    external_ids = data.get('external_ids')
    if not case_ids and not external_ids:
        raise UserError("Payload must include 'case_ids' or 'external_ids' fields")

    return _get_bulk_cases(request, case_ids=case_ids, external_ids=external_ids)


def _handle_list_view(request):
    res = get_list(request.domain, request.couch_user, request.GET)
    if 'next' in res:
        res['next'] = reverse('case_api', args=[request.domain], params=res['next'], absolute=True)
    return JsonResponse(res)


def _handle_ext_put(request, external_id):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UserError("Payload must be valid JSON")
    if not isinstance(data, dict):
        raise UserError("Payload must be a single JSON object")
    if 'external_id' not in data:
        data['external_id'] = external_id

    case = _get_by_external_id(request.domain, external_id)
    if case is None:
        is_creation = True
    else:
        is_creation = False
        if 'case_id' not in data:
            data['case_id'] = case.case_id
        elif data['case_id'] != case.case_id:
            raise UserError(
                'The given value of "case_id" does not match the existing value '
                f'for the case identified by external_id = "{external_id}". '
                '"case_id" is read-only and cannot be modified.'
            )

    return _handle_case_update(request, data, is_creation)


def _handle_case_put_post(request, is_creation, case_id=None):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UserError("Payload must be valid JSON")

    if not is_creation and case_id and 'case_id' not in data:
        data['case_id'] = case_id

    return _handle_case_update(request, data, is_creation)


def _handle_case_update(request, data, is_creation):
    filter_fields = get_fields_filter_fn(request.GET)
    try:
        xform, case_or_cases = handle_case_update(
            domain=request.domain,
            data=data,
            user=request.couch_user,
            device_id=request.META.get('HTTP_USER_AGENT'),
            is_creation=is_creation,
        )
    except PermissionDenied as e:
        return JsonResponse({'error': str(e)}, status=403)
    except SubmissionError as e:
        return JsonResponse({
            'error': str(e),
            'form_id': e.form_id,
        }, status=400)

    if isinstance(case_or_cases, list):
        return JsonResponse({
            'form_id': xform.form_id,
            'cases': [filter_fields(serialize_case(case)) for case in case_or_cases],
        })
    return JsonResponse({
        'form_id': xform.form_id,
        'case': filter_fields(serialize_case(case_or_cases)),
    })
