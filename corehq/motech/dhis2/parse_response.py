from operator import eq

from jsonpath_ng import Child, Fields, Slice, Where, Root
from django.utils.translation import gettext_lazy as _

from corehq.motech.openmrs.jsonpath import Cmp
from .const import ERROR_DIAGNOSIS


def get_errors(response: dict) -> dict:
    """
    Searches response from DHIS2 for import errors, and returns a
    dictionary of {jsonpath: error message}
    """
    if "response" in response:
        response = response["response"]

    errors = get_entity_errors(response)
    errors.update(get_enrollments_errors(response))
    errors.update(get_events_errors(response))
    return errors


def get_entity_errors(response: dict) -> dict:
    # $[?(@.status='ERROR')].description
    jsonpath_expr = Child(Where(
        Root(),
        Cmp(Fields("status"), eq, "ERROR")
    ), Fields("description"))
    # We write the JSONPath expression programmatically because
    # currently jsonpath-ng does not support parsing comparison
    # expressions like ``[?(@.status='ERROR')]``
    matches = jsonpath_expr.find(response)
    return {str(match.full_path): match.value for match in matches}


def get_enrollments_errors(response: dict) -> dict:
    # $.enrollments.importSummaries[*][?(@.status='ERROR')].description
    jsonpath_expr = Child(Where(Child(Child(
        Fields("enrollments"), Fields("importSummaries")), Slice()),
        Cmp(Fields("status"), eq, "ERROR")
    ), Fields("description"))
    matches = jsonpath_expr.find(response)
    return {str(match.full_path): match.value for match in matches}


def get_events_errors(response: dict) -> dict:
    # $.enrollments.importSummaries[*].events.importSummaries[*][?(@.status='ERROR')].description
    jsonpath_expr = Child(Where(Child(Child(Child(Child(Child(
        Fields("enrollments"), Fields("importSummaries")), Slice()),
        Fields("events")), Fields("importSummaries")), Slice()),
        Cmp(Fields("status"), eq, "ERROR")
    ), Fields("description"))
    matches = jsonpath_expr.find(response)
    return {str(match.full_path): match.value for match in matches}


def get_diagnosis_message(error: str) -> str:
    error_lower = error.lower()
    try:
        return next(v for k, v in ERROR_DIAGNOSIS.items() if k.lower() in error_lower)
    except StopIteration:
        return _('No diagnosis available for this error')
