import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext

from corehq.motech.generic_inbound.exceptions import GenericInboundUserError
from corehq.motech.generic_inbound.backend.base import BaseApiBackend
from corehq.motech.generic_inbound.utils import ApiResponse

JSON_CONTENT_TYPE = "application/json"


class JsonBackend(BaseApiBackend):
    """API backend for handling JSON payloads"""

    @classmethod
    def get_basic_error_response(cls, request_id, status_code, message):
        return _make_response(status_code, {'error': message})

    def get_success_response(self, response_json):
        return _make_response(200, response_json)

    def _get_body_for_eval_context(self):
        try:
            return json.loads(self.request_data.data)
        except json.JSONDecodeError:
            raise GenericInboundUserError(gettext("Payload must be valid JSON"))

    def _get_generic_error(self, status_code, message):
        return self.get_basic_error_response(self.request_data.request_id, status_code, message)

    def _get_submission_error_response(self, status_code, form_id, message):
        return _make_response(status_code, {
            'error': message,
            'form_id': form_id,
        })

    def _get_validation_error(self, status_code, message, errors):
        return _make_response(status_code, {
            'error': message,
            'errors': errors,
        })


def _make_response(status_code, internal_response):
    return ApiResponse(
        status=status_code,
        internal_response=internal_response,
        external_response=json.dumps(internal_response, cls=DjangoJSONEncoder),
        content_type=JSON_CONTENT_TYPE
    )
