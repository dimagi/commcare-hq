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
