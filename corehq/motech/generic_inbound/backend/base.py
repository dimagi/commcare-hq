from django.utils.translation import gettext as _

from corehq.apps.hqcase.api.core import SubmissionError, UserError, serialize_case
from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.motech.generic_inbound.exceptions import (
    GenericInboundApiError,
    GenericInboundRequestFiltered,
    GenericInboundUserError,
    GenericInboundValidationError,
)
from corehq.motech.generic_inbound.utils import get_evaluation_context, ApiResponse


class BaseApiBackend:
    """Base class for Generic API backend.

    Backend is used to translate incoming data to JSON which the API can process. The response
    is also translated from JSON to the appropriate data format."""

    @classmethod
    def get_basic_error_response(cls, request_id, status_code, message):
        """This method is intended to be used for errors that happen early in
        the process before the request data class has been created.

        It can also be used for basic errors that don't require additional context."""
        raise NotImplementedError

    def __init__(self, api_model, request_data):
        self.api_model = api_model
        self.request_data = request_data

    def run(self):
        try:
            response_json = _execute_generic_api(
                self.request_data.domain,
                self.request_data.couch_user,
                self.request_data.user_agent,
                self.get_context(),
                self.api_model,
            )
            return self.get_success_response(response_json)
        except GenericInboundRequestFiltered:
            return ApiResponse(status=204)
        except GenericInboundValidationError as e:
            return self._get_validation_error(400, 'validation error', e.errors)
        except SubmissionError as e:
            return self._get_submission_error_response(400, e.form_id, str(e))
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
            return self._get_generic_error(status, str(e))

    def get_context(self):
        return get_evaluation_context(
            self.request_data.restore_user,
            self.request_data.request_method,
            self.request_data.query,
            self.request_data.headers,
            self._get_body_for_eval_context()
        )

    def get_success_response(self, response_json):
        """Given a successful API response JSON, return an ``ApiResponse`` object."""
        raise NotImplementedError

    def _get_body_for_eval_context(self):
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


def _execute_generic_api(domain, couch_user, device_id, context, api_model):
    _apply_api_filter(api_model, context)
    _validate_api_request(api_model, context)

    data = api_model.parsed_expression(context.root_doc, context)

    if not isinstance(data, list):
        # the bulk API always requires a list
        data = [data]

    if not all(isinstance(item, dict) for item in data):
        raise GenericInboundApiError(_("Unexpected type for transformed request"))

    xform, cases = handle_case_update(
        domain=domain,
        data=data,
        user=couch_user,
        device_id=device_id,
        is_creation=None,
    )

    return {
        'form_id': xform.form_id,
        'cases': [serialize_case(case) for case in cases],
    }


def _apply_api_filter(api, eval_context):
    api_filter = api.parsed_filter
    if not api_filter:
        return False

    if not api_filter(eval_context.root_doc, eval_context):
        raise GenericInboundRequestFiltered()

    return True


def _validate_api_request(api, eval_context):
    """Run any validation expressions against the context.

    :returns: False if no expressions were run or True if all validations passed.
    :raises: GenericInboundValidationError if any validations fail"""
    validations = api.get_validations()
    if not validations:
        return False

    errors = []
    for validation in validations:
        expr = validation.parsed_expression
        if not expr(eval_context.root_doc, eval_context):
            errors.append(validation.get_error_context())

    if errors:
        raise GenericInboundValidationError(errors)

    return True
