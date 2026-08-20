"""HEAD/GET/PATCH API for a single form within an application.

A form's resource representation is its JSON fields plus its XForm XML
under ``source``. GET returns it with an ETag content hash; PATCH
requires that ETag back in ``If-Match``, so concurrent edits are
rejected rather than silently overwritten.

The ETag is the SHA-256 of exactly the bytes in the response body, which
are canonical JSON: keys sorted, no whitespace between tokens, non-ASCII
left unescaped, encoded as UTF-8. A client can therefore recompute the
ETag from a response it already holds instead of treating it as opaque.
"""
import dataclasses
import hashlib
import json
from dataclasses import dataclass

from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from jsonobject.exceptions import BadValueError
from memoized import memoized

from corehq.apps.api.decorators import api_throttle
from corehq.apps.app_manager.dbaccessors import get_app_doc, wrap_app
from corehq.apps.app_manager.exceptions import ModuleNotFoundException
from corehq.apps.app_manager.util import save_xform
from corehq.apps.domain.decorators import api_auth
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.util.view_utils import json_error

# ApiError.error codes
FORM_API_APP_NOT_FOUND = 'app_not_found'
FORM_API_MODULE_NOT_FOUND = 'module_not_found'
FORM_API_FORM_NOT_FOUND = 'form_not_found'
FORM_API_UNRECOGNIZED_FIELD = 'unrecognized_field'
FORM_API_INVALID_FIELD_VALUE = 'invalid_field_value'
FORM_API_DOC_TYPE_MISMATCH = 'doc_type_mismatch'
FORM_API_PRECONDITION_REQUIRED = 'precondition_required'
FORM_API_PRECONDITION_FAILED = 'precondition_failed'
FORM_API_CONFLICT = 'conflict'

ETAG = 'etag'

_ERROR_TO_STATUS_CODE = {
    FORM_API_APP_NOT_FOUND: 404,
    FORM_API_MODULE_NOT_FOUND: 404,
    FORM_API_FORM_NOT_FOUND: 404,
}


@dataclass
class ApiResult:
    """The outcome of an API operation. Functions that also produce a
    value return it alongside one of these, rather than through it.
    """

    errors: 'list[ApiError]' = dataclasses.field(default_factory=list)

    @property
    def success(self):
        return not self.errors

    @classmethod
    def error(cls, code, message):
        return cls([ApiError(code, message)])


@dataclass
class ApiError:
    error: str
    message: str

    def to_json(self):
        return dataclasses.asdict(self)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(json_error, name='dispatch')
@method_decorator(api_throttle, name='dispatch')
class SingleFormApiView(View):
    """HEAD/GET/PATCH a single form's JSON fields and XForm XML."""

    @method_decorator(require_permission(HqPermissions.view_apps, login_decorator=api_auth()))
    def head(self, request, domain, app_id, module_id, form_id):
        form, result = get_form_for_api(domain, app_id, module_id, form_id)
        if not result.success:
            return HttpResponse(status=_status_for_result(result))

        response = HttpResponse(status=200)
        response[ETAG] = FormResource(form).get_etag()
        return response

    @method_decorator(require_permission(HqPermissions.view_apps, login_decorator=api_auth()))
    def get(self, request, domain, app_id, module_id, form_id):
        form, result = get_form_for_api(domain, app_id, module_id, form_id)
        if not result.success:
            return _errors_response(result)

        return FormResource(form).get_response()


def _errors_response(result):
    return JsonResponse(
        {'errors': [error.to_json() for error in result.errors]},
        status=_status_for_result(result),
    )


def _status_for_result(result):
    return _ERROR_TO_STATUS_CODE[result.errors[0].error]


class FormResource:
    """A form's API representation: the exact bytes sent to clients, and
    an ETag over those same bytes.

    Each accessor is memoized and they build on one another, so a caller
    that needs only the ETag does the serialization once and a caller
    that needs the whole response does not repeat it. An instance must
    not outlive a change to ``form``, or it will serve the memoized
    representation of the older version -- build one where it is needed
    rather than passing it around.
    """

    def __init__(self, form):
        self.form = form

    def get_response(self, status=200):
        response = HttpResponse(
            self.get_body(), status=status, content_type='application/json'
        )
        response[ETAG] = self.get_etag()
        return response

    @memoized
    def get_etag(self):
        return '"{}"'.format(hashlib.sha256(self.get_body()).hexdigest())

    @memoized
    def get_body(self):
        return json.dumps(
            _form_resource_dict(self.form),
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            cls=DjangoJSONEncoder,
        ).encode('utf-8')


def patch_form_for_api(domain, app_id, module_id, form_id, source, if_match):
    form, result = get_form_for_api(domain, app_id, module_id, form_id)
    if not result.success:
        return None, result

    errors = []
    current_etag = FormResource(form).get_etag()
    if if_match is None:
        errors.append(ApiError(
            FORM_API_PRECONDITION_REQUIRED, 'If-Match header is required.'
        ))
    elif if_match != current_etag:
        errors.append(ApiError(
            FORM_API_PRECONDITION_FAILED, 'If-Match does not match the current ETag.'
        ))

    source_xml = source.get('source')
    if source_xml is not None and not isinstance(source_xml, str):
        errors.append(ApiError(
            FORM_API_INVALID_FIELD_VALUE, 'source must be a string'
        ))

    fields_to_set, patch_errors = create_form_patch(form, source)
    if patch_errors:
        errors.extend(patch_errors)

    if errors:
        return None, ApiResult(errors)

    try:
        for key, value in fields_to_set.items():
            setattr(form, key, value)
    except (ValueError, BadValueError) as e:
        return None, ApiResult.error(FORM_API_INVALID_FIELD_VALUE, str(e))

    app = form.get_app()
    if source_xml is not None:
        save_xform(app, form, source_xml.encode('utf-8'))

    try:
        app.save()
    except ResourceConflict:
        return None, ApiResult.error(
            FORM_API_CONFLICT, 'Application was concurrently modified, please retry'
        )

    return form, ApiResult()


def get_form_for_api(domain, app_id, module_id, form_id):
    try:
        app_doc = get_app_doc(domain, app_id)
    except ResourceNotFound:
        app_doc = None

    # A saved build is a frozen copy, and is no more addressable than an
    # app that does not exist at all.
    if app_doc is None or app_doc.get('copy_of'):
        return None, ApiResult.error(FORM_API_APP_NOT_FOUND, f"Application ({app_id}) not found")

    app = wrap_app(app_doc)

    try:
        module = app.get_module_by_unique_id(module_id)
    except ModuleNotFoundException:
        return None, ApiResult.error(FORM_API_MODULE_NOT_FOUND, f"Module ({module_id}) not found")

    form = module.get_form_by_unique_id(form_id)
    if form is None:
        return None, ApiResult.error(FORM_API_FORM_NOT_FOUND, f"Module ({module_id}) not found")

    return form, ApiResult()


def create_form_patch(form, source):
    """Return ``(fields_to_set, errors)`` -- the subset of ``source`` that's
    valid to apply to ``form``, as a plain ``{attr_name: value}`` dict.

    ``unique_id`` and ``xmlns`` in ``source`` are silently dropped (never
    settable). ``source`` should be set separately using ``save_xform``.

    ``doc_type`` in ``source`` is checked against
    ``form``'s actual type -- mismatch returns ``doc_type_mismatch``, a
    match is dropped like the other two identity fields.

    Every other key must be a recognized property of ``form``'s schema, or
    this returns ``unrecognized_field``.
    """
    valid_fields = set(type(form).properties().keys())
    fields_to_set = {}
    errors = []

    for key, value in source.items():
        if key in ('unique_id', 'xmlns', 'source'):
            continue
        if key == 'doc_type':
            if value != form.doc_type:
                errors.append(ApiError(
                    FORM_API_DOC_TYPE_MISMATCH,
                    f"Form doc_type '{value}' does not match existing doc_type '{form.doc_type}'",
                ))
            continue
        if key not in valid_fields:
            errors.append(ApiError(
                FORM_API_UNRECOGNIZED_FIELD, f"'{key}' is not a recognized field"
            ))
        else:
            fields_to_set[key] = value
    if errors:
        return None, errors

    return fields_to_set, []


def _form_resource_dict(form):
    """The single-form-API's resource representation of ``form`` -- its
    JSON fields plus its XForm XML under ``source``.

    ``validation_cache`` is dropped. Assigning that attribute writes a
    dynamic property onto the document as well as to the Django cache it
    is declared against, so every in-memory form carries the key, while
    one reloaded from Couch has it stripped by ``FormBase.wrap``.
    Leaving it in would make the ETag depend on where the form was
    obtained rather than on its content.
    """
    resource = form.to_json()
    resource.pop('validation_cache', None)
    resource['source'] = form.source
    return resource
