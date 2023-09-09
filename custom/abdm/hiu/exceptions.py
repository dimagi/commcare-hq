from drf_standardized_errors.handler import exception_handler as drf_standardized_exception_handler
from rest_framework.response import Response

from custom.abdm.exceptions import ABDMErrorResponseFormatter

HIU_ERROR_MESSAGES = {
    4400: "Required attributes not provided or Request information is not as expected",
    4401: "Unauthorized request",
    4404: "Resource not found",
    4405: "Method not allowed",
    4407: "Patient details not found",
    4410: "Expired Key Pair",
    4416: "Consent Artefact Not Found",
    4418: "Consent has expired",
    4500: "Unknown error occurred",
    4503: "Gateway Service down",
    4554: "Error received from Gateway",
    4555: "Health information not received from Provider in the time limit. Please try again!"
}


class HIUErrorResponseFormatter(ABDMErrorResponseFormatter):
    error_code_prefix = '4'
    error_messages = HIU_ERROR_MESSAGES


def hiu_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return HIUErrorResponseFormatter().format_drf_response(response)


def hiu_gateway_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return HIUErrorResponseFormatter().format_drf_response(response, error_details=True)

