import logging

from functools import wraps
from typing import List

from custom.abdm.milestone_one.utils.response_handler import generate_invalid_req_response

logger = logging.getLogger(__name__)


def required_request_params(params: List[str]):
    """
    A version of the requires_privilege decorator which raises an Http404
    if PermissionDenied is raised.
    """
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if not (params and isinstance(params, List)):
                error_msg = f"Request {request} could not be validated as validation input not provided."
                logger.warning(error_msg)
                return generate_invalid_req_response(error_msg)
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
