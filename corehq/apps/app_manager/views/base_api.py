from django.http import JsonResponse

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
FORM_API_INVALID_JSON = 'invalid_json'

# ApiError.error codes -> HTTP status code.
ERROR_TO_STATUS_CODE = {
    FORM_API_APP_NOT_FOUND: 404,
    FORM_API_MODULE_NOT_FOUND: 404,
    FORM_API_FORM_NOT_FOUND: 404,
    FORM_API_UNRECOGNIZED_FIELD: 400,
    FORM_API_INVALID_FIELD_VALUE: 400,
    FORM_API_DOC_TYPE_MISMATCH: 422,
    FORM_API_PRECONDITION_REQUIRED: 428,
    FORM_API_PRECONDITION_FAILED: 412,
    FORM_API_CONFLICT: 409,
    FORM_API_INVALID_JSON: 400,
}


def status_for_result(result):
    return ERROR_TO_STATUS_CODE[result.errors[0].error]


def errors_response(result):
    return JsonResponse(
        {'errors': [error.to_json() for error in result.errors]},
        status=status_for_result(result),
    )
