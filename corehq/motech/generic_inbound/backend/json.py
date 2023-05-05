import json

from django.utils.translation import gettext

from corehq.motech.generic_inbound.exceptions import GenericInboundUserError
from corehq.motech.generic_inbound.backend.base import BaseApiBackend
from corehq.motech.generic_inbound.utils import ApiResponse


class JsonBackend(BaseApiBackend):
    """API backend for handling JSON payloads"""

    def get_success_response(self, response_json):
        return ApiResponse(status=200, internal_response=response_json)

    def _get_body_for_eval_context(self):
        try:
            return json.loads(self.request_data.data)
        except json.JSONDecodeError:
            raise GenericInboundUserError(gettext("Payload must be valid JSON"))

    def _get_generic_error(self, status_code, message):
        return ApiResponse(status=status_code, internal_response={'error': message})

    def _get_submission_error_response(self, status_code, form_id, message):
        return ApiResponse(status=status_code, internal_response={
            'error': message,
            'form_id': form_id,
        })

    def _get_validation_error(self, status_code, message, errors):
        return ApiResponse(status=status_code, internal_response={
            'error': message,
            'errors': errors,
        })
