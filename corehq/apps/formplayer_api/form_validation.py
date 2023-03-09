import jsonobject
import requests
from requests import HTTPError, RequestException

from dimagi.utils.logging import notify_exception

from corehq.apps.formplayer_api import const
from corehq.apps.formplayer_api.exceptions import (
    FormplayerAPIException,
    FormplayerRequestException,
)
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.util.hmac_request import get_hmac_digest
from django.conf import settings


class ValidationAPIProblem(jsonobject.JsonObject):
    type = jsonobject.StringProperty(choices=[
        "error", "markup", "invalid-structure", "dangerous", "technical"])
    message = jsonobject.StringProperty()
    fatal = jsonobject.BooleanProperty()


class ValidationAPIResult(jsonobject.JsonObject):
    validated = jsonobject.BooleanProperty()
    fatal_error = jsonobject.StringProperty()
    fatal_error_expected = jsonobject.BooleanProperty()
    problems = jsonobject.ListProperty(ValidationAPIProblem)


class FormValidationResult(object):
    def __init__(self, problems, success, fatal_error):
        self.problems = problems
        self.success = success
        self.fatal_error = fatal_error

    def to_json(self):
        return {
            'problems': self.problems,
            'success': self.success,
            'fatal_error': self.fatal_error,
        }


def validate_form(form_xml):
    try:
        response = requests.post(
            get_formplayer_url() + const.ENDPOINT_VALIDATE_FORM,
            data=form_xml,
            headers={
                'Content-Type': 'application/xml',
                'X-MAC-DIGEST': get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, form_xml),
            }
        )
    except RequestException as e:
        notify_exception(None, "Error calling Formplayer form validation endpoint")
        raise FormplayerAPIException(e) from e

    try:
        response.raise_for_status()
    except HTTPError:
        notify_exception(None, "Error calling Formplayer form validation endpoint", details={
            'status_code': response.status_code
        })
        raise FormplayerRequestException(response.status_code)

    api_result = ValidationAPIResult(response.json())
    result = FormValidationResult(
        problems=[problem.to_json() for problem in api_result.problems],
        success=api_result.validated,
        fatal_error=api_result.fatal_error,
    )
    return result
