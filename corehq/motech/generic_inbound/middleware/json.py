import json

from django.utils.translation import gettext

from corehq.motech.generic_inbound.exceptions import GenericInboundUserError
from corehq.motech.generic_inbound.utils import get_evaluation_context, ApiResponse


class JsonMiddleware:

    def get_context(self, request_data):
        return get_evaluation_context(
            request_data.restore_user,
            request_data.request_method,
            request_data.query,
            request_data.headers,
            self.convert_data(request_data.data)
        )

    def get_success_response(self, response_json):
        return ApiResponse(status=200, data=response_json)

    def get_error_response(self, status, message):
        return ApiResponse(status=status, data={'error': message})

    def get_submission_error_response(self, status, form_id, message):
        return ApiResponse(status=status, data={
            'error': message,
            'form_id': form_id,
        })

    def get_validation_error(self, status, message, errors):
        return ApiResponse(status=status, data={
            'error': message,
            'errors': errors,
        })

    def convert_data(self, data):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            raise GenericInboundUserError(gettext("Payload must be valid JSON"))
