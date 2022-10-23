import logging

from functools import wraps
from typing import List

from custom.abdm.milestone_one.utils.response_handler import generate_invalid_req_response

logger = logging.getLogger(__name__)


def required_request_params(params):
    """
    Checks if the parameters provided in the decorator(a list of strings) are present in the DRF request.
    If not, raises 400 Bad Request error.
    """

    def decorate(fn):
        if not (params and isinstance(params, List)):
            error_msg = "Request could not be validated as a valid input not provided. \
                Required: List of parameters."
            logger.warning(error_msg)
            return generate_invalid_req_response(error_msg)

        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            invalid_params = []
            for param in params:
                if not request.data.get(param):
                    invalid_params.append(param)
            if invalid_params:
                error_msg = f"Missing required parameter(s) in the request: {','.join(invalid_params)}"
                return generate_invalid_req_response(error_msg)
            return fn(request, *args, **kwargs)

        return wrapped

    return decorate
