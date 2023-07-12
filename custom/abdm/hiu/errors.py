from drf_standardized_errors.handler import exception_handler as drf_standardized_exception_handler
from custom.abdm.errors import ABDMBaseResponseFormatter
from rest_framework.exceptions import APIException


HIU_ERROR_MESSAGES = {
    4400: "Required attributes not provided or Request information is not as expected",
    4500: "Unknown error occurred"
}


class HIUResponseFormatter(ABDMBaseResponseFormatter):
    error_code_prefix = '4'
    error_messages = HIU_ERROR_MESSAGES


def hiu_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return HIUResponseFormatter().format_response(response)


class ABDMServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'ABDM Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'


class ABDMGatewayError(APIException):
    status_code = 554
    default_detail = 'Error from Gateway'
    default_code = 'gateway_error'

