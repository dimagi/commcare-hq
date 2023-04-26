import json
from contextlib import contextmanager

from django.utils.translation import gettext

from corehq.apps.hqcase.api.core import SubmissionError, UserError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.motech.generic_inbound.exceptions import GenericInboundUserError, GenericInboundRequestFiltered, \
    GenericInboundValidationError, GenericInboundApiError
from corehq.motech.generic_inbound.utils import get_evaluation_context, ApiResponse


class JsonMiddleware:
    error_response = None

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

    def get_generic_error(self, status, message):
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

    @contextmanager
    def handle_errors(self):
        try:
            yield
        except GenericInboundRequestFiltered:
            self.error_response = ApiResponse(status=204)
        except GenericInboundValidationError as e:
            self.error_response = self.get_validation_error(400, 'validation error', e.errors)
        except SubmissionError as e:
            self.error_response = self.get_submission_error_response(400, e.form_id, str(e))
        except Exception as e:
            try:
                status = {
                    UserError: 400,
                    BadSpecError: 500,
                    GenericInboundUserError: 400,
                    GenericInboundApiError: 500,
                }[type(e)]
            except KeyError:
                raise e
            self.error_response = self.get_generic_error(status, str(e))

    def get_error_response(self):
        return self.error_response
