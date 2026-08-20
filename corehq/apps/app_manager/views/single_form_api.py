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

from django.core.serializers.json import DjangoJSONEncoder
from couchdbkit.exceptions import ResourceNotFound
from memoized import memoized

from corehq.apps.app_manager.dbaccessors import get_app_doc, wrap_app
from corehq.apps.app_manager.exceptions import ModuleNotFoundException

# ApiError.error codes
FORM_API_APP_NOT_FOUND = 'app_not_found'
FORM_API_MODULE_NOT_FOUND = 'module_not_found'
FORM_API_FORM_NOT_FOUND = 'form_not_found'


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
