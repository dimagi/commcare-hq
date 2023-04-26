from contextlib import contextmanager

from corehq.apps.hqcase.api.core import SubmissionError, UserError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.motech.generic_inbound.exceptions import (
    GenericInboundApiError,
    GenericInboundRequestFiltered,
    GenericInboundUserError,
    GenericInboundValidationError,
)
from corehq.motech.generic_inbound.utils import get_evaluation_context, ApiResponse


class BaseApiMiddleware:
    """Base class for Generic API middleware.

    Middleware is used to translate incoming data to JSON which the API can process. The response
    is also translated from JSON to the appropriate data format."""
    error_response = None

    def get_context(self, request_data):
        return get_evaluation_context(
            request_data.restore_user,
            request_data.request_method,
            request_data.query,
            request_data.headers,
            self._get_body_for_eval_context(request_data)
        )

    @contextmanager
    def handle_errors(self):
        """Context manager for handling errors during execution of the API.

        If an error is handled use ``get_error_response`` to get the ApiResponse.
        """
        try:
            yield
        except GenericInboundRequestFiltered:
            self.error_response = ApiResponse(status=204)
        except GenericInboundValidationError as e:
            self.error_response = self._get_validation_error(400, 'validation error', e.errors)
        except SubmissionError as e:
            self.error_response = self._get_submission_error_response(400, e.form_id, str(e))
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
            self.error_response = self._get_generic_error(status, str(e))

    def get_error_response(self):
        """In an error is handled by the ``handle_errors`` context manager, the response will be
        available here."""
        return self.error_response

    def get_success_response(self, response_json):
        """Given a successful API response JSON, return an ``ApiResponse`` object."""
        raise NotImplementedError

    def _get_body_for_eval_context(self, request_data):
        """Give the RequestData, return a dictionary of data which will be placed into the ``body``
        attribute of the evaluation context.
        """
        raise NotImplementedError

    def _get_generic_error(self, status_code, message):
        """Return an ApiResponse object with the given status code and message."""
        raise NotImplementedError

    def _get_submission_error_response(self, status_code, form_id, message):
        """Return an ApiResponse object or a submission processing error."""
        raise NotImplementedError

    def _get_validation_error(self, status_code, message, errors):
        """Return an ApiResponse object for validation errors."""
        raise NotImplementedError
