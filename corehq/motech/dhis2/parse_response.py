from operator import eq

from jsonpath_ng import Child, Fields, Slice, Where, Root

from corehq.motech.openmrs.jsonpath import Cmp


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
