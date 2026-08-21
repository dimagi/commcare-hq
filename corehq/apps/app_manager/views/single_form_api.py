import dataclasses
import hashlib
import json
from dataclasses import dataclass

from couchdbkit.exceptions import ResourceNotFound
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from memoized import memoized

from corehq import toggles
from corehq.apps.api.decorators import api_throttle
from corehq.apps.app_manager.dbaccessors import get_app_doc, wrap_app
from corehq.apps.app_manager.exceptions import (
    ModuleNotFoundException,
)
from corehq.apps.domain.decorators import api_auth
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.util.view_utils import json_error

# ApiError.error codes
FORM_API_APP_NOT_FOUND = 'app_not_found'
FORM_API_MODULE_NOT_FOUND = 'module_not_found'
FORM_API_FORM_NOT_FOUND = 'form_not_found'

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
