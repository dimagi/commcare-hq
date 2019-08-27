import jsonobject
import requests
from requests import HTTPError
from requests import RequestException

from corehq.apps.formplayer_api import const
from corehq.apps.formplayer_api.exceptions import FormplayerRequestException, FormplayerAPIException
from corehq.apps.formplayer_api.utils import get_formplayer_url
from dimagi.utils.logging import notify_exception


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
            headers={'Content-Type': 'application/xml'}
        )
    except RequestException as e:
        notify_exception(None, "Error calling Formplayer form validation endpoint")
        raise FormplayerAPIException(e)

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
