from drf_standardized_errors.handler import exception_handler as drf_standardized_exception_handler

from custom.abdm.exceptions import ABDMErrorResponseFormatter


# TODO Consider using variables for error codes
HIP_ERROR_MESSAGES = {
    3400: "Required attributes not provided or Request information is not as expected",
    3401: "Unauthorized request",
    3404: "Resource not found",
    3405: "Method not allowed",
    3500: "Unknown error occurred",
    3503: "Gateway Service down",
    3554: "Error received from Gateway",
    3407: "Patient details not found",
    3416: "Consent Artefact Not Found",
    3417: "Invalid Consent Status",
    3418: "Consent has expired",
    3419: "Date range is not valid",
}


class HIPErrorResponseFormatter(ABDMErrorResponseFormatter):
    error_code_prefix = '3'
    error_messages = HIP_ERROR_MESSAGES


def hip_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return HIPErrorResponseFormatter().format(response)


def hip_gateway_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return HIPErrorResponseFormatter().format(response, error_details=True)
