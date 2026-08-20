from django.http import JsonResponse

# ApiError.error codes -> HTTP status code.
ERROR_TO_STATUS_CODE = {
    'app_not_found': 404,
    'module_not_found': 404,
    'form_not_found': 404,
    'unrecognized_field': 400,
    'invalid_field_value': 400,
    'doc_type_mismatch': 422,
    'precondition_required': 428,
    'precondition_failed': 412,
    'conflict': 409,
    'invalid_json': 400,
}


def status_for_result(result):
    return ERROR_TO_STATUS_CODE[result.errors[0].error]


def errors_response(result):
    return JsonResponse(
        {'errors': [error.to_json() for error in result.errors]},
        status=status_for_result(result),
    )
