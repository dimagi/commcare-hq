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
from dataclasses import dataclass

from couchdbkit.exceptions import ResourceNotFound

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
