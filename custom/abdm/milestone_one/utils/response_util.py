from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

success_response_keys = ["txnId", "healthIdNumber", "auth_methods", "token",
                         "health_card", "health_id", "authMethods"]


def parse_response(response_data):
    if not response_data:
        return Response({"error": "No valid response found"}, status=HTTP_500_INTERNAL_SERVER_ERROR)
    if any([key in response_data for key in success_response_keys]):
        return _get_success_abdm_response(response_data)
    return _get_error_abdm_response(response_data)


def generate_invalid_req_response(message, response_code=HTTP_400_BAD_REQUEST):
    resp = {
        "code": str(response_code),
        "message": "Unable to process the current request due to incorrect data entered.",
        "details": [{
            "message": message,
            "attribute": None
        }]
    }
    return Response(resp, status=HTTP_400_BAD_REQUEST)


def _get_success_abdm_response(response_data):
    return Response(response_data, status=HTTP_200_OK)


def _get_error_abdm_response(response_data):
    if "code" in response_data:
        return _parse_response(response_data)
    return generate_invalid_req_response(response_data)


def _parse_response(response_data):
    status_code = int(response_data.get("code").split("-")[-1])
    return Response(response_data, status=status_code)
