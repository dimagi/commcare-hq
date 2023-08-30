from drf_standardized_errors.handler import exception_handler as drf_standardized_exception_handler
from rest_framework.response import Response

from custom.abdm.exceptions import ABDMErrorResponseFormatter

HIU_ERROR_MESSAGES = {
    4400: "Required attributes not provided or Request information is not as expected",
    4401: "Unauthorized request",
    4404: "Resource not found",
    4405: "Method not allowed",
    4500: "Unknown error occurred",
    4503: "Gateway Service down",
    4554: "Error received from Gateway",
    4407: "Patient details not found",
    4451: "Consent has expired",
}


class HIUErrorResponseFormatter(ABDMErrorResponseFormatter):
    error_code_prefix = '4'
    error_messages = HIU_ERROR_MESSAGES


def hiu_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return HIUErrorResponseFormatter().format(response)


def hiu_gateway_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return HIUErrorResponseFormatter().format(response, error_details=True)


def send_custom_error_response(error_code, status_code=400, details_message=None, details_field=None):
    data = {
        'error': {
            'code': error_code,
            'message': HIU_ERROR_MESSAGES.get(error_code)
        }
    }
    if details_message or details_field:
        data['error']['details'] = [{
            'code': 'invalid',
            'detail': details_message or HIU_ERROR_MESSAGES.get(error_code),
            'attr': details_field
        }]
    return Response(data=data, status=status_code)
