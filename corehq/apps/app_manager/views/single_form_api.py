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

from corehq import toggles
from corehq.apps.api.decorators import api_throttle
from corehq.apps.app_manager.dbaccessors import get_app_doc, wrap_app
from corehq.apps.app_manager.exceptions import (
    DangerousXmlException,
    LockedQuestionError,
    ModuleNotFoundException,
)
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.views.forms import check_locked_questions_unmodified
from corehq.apps.app_manager.xform import XForm, XFormException
from corehq.apps.domain.decorators import api_auth
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.util.view_utils import json_error

# ApiError.error codes
FORM_API_APP_NOT_FOUND = 'app_not_found'
FORM_API_MODULE_NOT_FOUND = 'module_not_found'
FORM_API_FORM_NOT_FOUND = 'form_not_found'
FORM_API_FIELD_NOT_PATCHABLE = 'field_not_patchable'
FORM_API_INVALID_FIELD_VALUE = 'invalid_field_value'
FORM_API_PRECONDITION_REQUIRED = 'precondition_required'
FORM_API_PRECONDITION_FAILED = 'precondition_failed'
FORM_API_CONFLICT = 'conflict'
FORM_API_INVALID_JSON = 'invalid_json'
FORM_API_LOCKED_QUESTION = 'locked_question'

# Only these may be changed. Every other field of a form carries an
# invariant the schema does not express -- a derived value, a uniqueness
# rule, a dependency on a sibling field, a paid-feature gate -- and each
# would need its own guard here. ``source`` is on the list but travels
# its own path, since it is an attachment rather than a schema property.
PATCHABLE_FIELDS = frozenset({'name', 'comment', 'source'})

ETAG = 'etag'

_ERROR_TO_STATUS_CODE = {
    FORM_API_APP_NOT_FOUND: 404,
    FORM_API_MODULE_NOT_FOUND: 404,
    FORM_API_FORM_NOT_FOUND: 404,
    FORM_API_FIELD_NOT_PATCHABLE: 400,
    FORM_API_INVALID_FIELD_VALUE: 400,
    FORM_API_PRECONDITION_REQUIRED: 428,
    FORM_API_PRECONDITION_FAILED: 412,
    FORM_API_CONFLICT: 409,
    FORM_API_INVALID_JSON: 400,
    FORM_API_LOCKED_QUESTION: 403,
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
class SingleFormApiView(View):
    """HEAD/GET/PATCH a single form's JSON fields and XForm XML."""

    def dispatch(self, request, *args, **kwargs):
        # Rolling out by domain. Until this is generally available the flag
        # also bounds who can reach an endpoint that does not yet check
        # access_api, unlike the rest of the APIs here.
        if not toggles.SINGLE_FORM_API.enabled(kwargs.get('domain')):
            return HttpResponse(status=404)
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(require_permission(HqPermissions.view_apps, login_decorator=api_auth()))
    @method_decorator(api_throttle)
    def head(self, request, domain, app_id, module_id, form_id):
        form, result = get_form_for_api(domain, app_id, module_id, form_id)
        if not result.success:
            return HttpResponse(
                status=_status_for_result(result), content_type='application/json'
            )

        response = HttpResponse(status=200, content_type='application/json')
        response[ETAG] = FormResource(form).get_etag()
        return response

    @method_decorator(require_permission(HqPermissions.view_apps, login_decorator=api_auth()))
    @method_decorator(api_throttle)
    def get(self, request, domain, app_id, module_id, form_id):
        form, result = get_form_for_api(domain, app_id, module_id, form_id)
        if not result.success:
            return _errors_response(result)

        return FormResource(form).get_response()

    @method_decorator(require_permission(HqPermissions.edit_apps, login_decorator=api_auth()))
    @method_decorator(api_throttle)
    def patch(self, request, domain, app_id, module_id, form_id):
        try:
            source = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            source = None
        if not isinstance(source, dict):
            return _errors_response(
                ApiResult.error(FORM_API_INVALID_JSON, 'Invalid JSON body')
            )

        if_match = request.headers.get('If-Match')

        form, result = patch_form_for_api(
            domain, app_id, module_id, form_id, source, if_match, request.couch_user
        )
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

    The bytes are canonical JSON -- keys sorted, no whitespace between
    tokens, non-ASCII left unescaped, encoded as UTF-8 -- so a client can
    recompute the ETag from a response it holds rather than treat it as
    opaque.

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


def patch_form_for_api(domain, app_id, module_id, form_id, source, if_match, couch_user):
    form, result = get_form_for_api(domain, app_id, module_id, form_id)
    if not result.success:
        return None, result

    errors = []
    if if_match is None:
        errors.append(ApiError(
            FORM_API_PRECONDITION_REQUIRED, 'If-Match header is required.'
        ))
    elif not if_match_is_satisfied(if_match, FormResource(form).get_etag()):
        errors.append(ApiError(
            FORM_API_PRECONDITION_FAILED, 'If-Match does not match the current ETag.'
        ))

    source_xml = source.get('source')
    if 'source' in source and source_xml is None:
        errors.append(ApiError(
            FORM_API_INVALID_FIELD_VALUE, 'source cannot be deleted'
        ))
    elif source_xml is not None and not isinstance(source_xml, str):
        errors.append(ApiError(
            FORM_API_INVALID_FIELD_VALUE, 'source must be a string'
        ))
    elif source_xml is not None and form.form_type == 'shadow_form':
        errors.append(ApiError(
            FORM_API_INVALID_FIELD_VALUE,
            'a shadow form takes its XML from the form it shadows',
        ))
    elif source_xml is not None:
        # save_xform swallows a parse failure and stores the string anyway,
        # which would leave the form with no xmlns and break submission
        # routing, so the XML has to be rejected before it gets that far.
        try:
            xform = XForm(source_xml.encode('utf-8'), domain=domain)
            if not xform.exists():
                raise XFormException('the document contains no XForm')
            xform.data_node  # what save_xform reads; fail here instead, cleanly
        except (XFormException, DangerousXmlException) as e:
            errors.append(ApiError(
                FORM_API_INVALID_FIELD_VALUE, f'source is not a valid XForm: {e}'
            ))

    resource = _form_resource_dict(form)
    resource.pop('source', None)  # an attachment, not a schema property

    patch = {}
    for key, value in source.items():
        if key == 'source':
            continue  # an attachment; applied through save_xform below
        elif key in PATCHABLE_FIELDS:
            patch[key] = value
        elif value == resource.get(key):
            continue  # sent back unchanged, so nothing to refuse
        else:
            errors.append(ApiError(
                FORM_API_FIELD_NOT_PATCHABLE, f"'{key}' cannot be changed"
            ))

    if errors:
        return None, ApiResult(errors)

    if source_xml is not None:
        try:
            check_locked_questions_unmodified(
                couch_user, domain, form, source_xml.encode('utf-8')
            )
        except LockedQuestionError:
            return None, ApiResult.error(
                FORM_API_LOCKED_QUESTION,
                'This form contains locked questions that you may not modify.',
            )

    try:
        patched = type(form).wrap(merge_patch(resource, patch))
    except (ValueError, BadValueError) as e:
        return None, ApiResult.error(FORM_API_INVALID_FIELD_VALUE, str(e))

    module = form.get_module()
    module.forms[form.id] = patched
    # re-read it through the getter, which is what parents the form to
    # its module -- ``source`` and ``get_app`` both need that link
    patched = module.get_form(form.id)

    app = patched.get_app()
    if source_xml is not None:
        save_xform(app, patched, source_xml.encode('utf-8'))

    try:
        app.save()
    except ResourceConflict:
        return None, ApiResult.error(
            FORM_API_CONFLICT, 'Application was concurrently modified, please retry'
        )

    return patched, ApiResult()


def get_form_for_api(domain, app_id, module_id, form_id):
    try:
        app_doc = get_app_doc(domain, app_id)
    except ResourceNotFound:
        app_doc = None

    # Only a live, editable Application is addressable. A saved build is a
    # frozen copy; a deleted app is 'Application-Deleted'; a RemoteApp has no
    # modules at all; a LinkedApplication is overwritten by its next sync.
    # None of them is any more addressable than an app that does not exist.
    if (
        app_doc is None
        or app_doc.get('copy_of')
        or app_doc.get('doc_type') != 'Application'
    ):
        return None, ApiResult.error(FORM_API_APP_NOT_FOUND, f"Application ({app_id}) not found")

    app = wrap_app(app_doc)

    try:
        module = app.get_module_by_unique_id(module_id)
    except ModuleNotFoundException:
        return None, ApiResult.error(FORM_API_MODULE_NOT_FOUND, f"Module ({module_id}) not found")

    form = module.get_form_by_unique_id(form_id)
    if form is None:
        return None, ApiResult.error(FORM_API_FORM_NOT_FOUND, f"Form ({form_id}) not found")

    return form, ApiResult()


def if_match_is_satisfied(if_match, current_etag):
    """Whether ``If-Match`` permits the write, per RFC 9110 section 13.1.1.

    The header carries a list of entity tags, or ``*`` for any current
    representation. Comparison is strong, so a weak validator never
    matches.
    """
    if if_match.strip() == '*':
        return True
    return any(tag.strip() == current_etag for tag in if_match.split(','))


def merge_patch(target, patch):
    """Apply ``patch`` to ``target`` per RFC 7396 JSON Merge Patch.

    Objects merge key by key, a ``null`` removes its key, and anything
    else -- including a list -- replaces what was there.
    """
    if not isinstance(patch, dict):
        return patch
    if not isinstance(target, dict):
        target = {}
    merged = dict(target)
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = merge_patch(merged.get(key), value)
    return merged


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
    if form.form_type != 'shadow_form':
        # A shadow form has no XML of its own: ``source`` regenerates it from
        # the form it shadows on every read, so including it would make the
        # ETag differ between two identical GETs and no PATCH could ever
        # satisfy If-Match.
        resource['source'] = form.source
    return resource
