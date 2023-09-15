from drf_standardized_errors.handler import \
    exception_handler as drf_standardized_exception_handler

from custom.abdm.exceptions import ABDMErrorResponseFormatter

USER_AUTH_ERROR_MESSAGES = {
    1400: "Required attributes not provided or Request information is not as expected",
    1401: "Unauthorized request",
    1404: "Resource not found",
    1405: "Method not allowed",
    1500: "Unknown error occurred",
    1503: "Gateway Service down",
    1554: "Error received from Gateway",
    1555: "Gateway callback response timeout",
}


class UserAuthErrorResponseFormatter(ABDMErrorResponseFormatter):
    error_code_prefix = '1'
    error_messages = USER_AUTH_ERROR_MESSAGES


def user_auth_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return UserAuthErrorResponseFormatter().format(response)


def user_auth_gateway_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return UserAuthErrorResponseFormatter().format(response, error_details=True)
