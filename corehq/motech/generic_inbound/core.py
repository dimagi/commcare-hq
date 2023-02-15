from django.utils.translation import gettext as _

from corehq.apps.hqcase.api.core import (
    SubmissionError,
    UserError,
    serialize_case,
)
from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.motech.generic_inbound.exceptions import (
    GenericInboundApiError,
    GenericInboundRequestFiltered,
    GenericInboundValidationError,
)
from corehq.motech.generic_inbound.utils import ApiResponse


def execute_generic_api(api_model, request_data):
    try:
        response_json = _execute_generic_api(
            request_data.domain,
            request_data.couch_user,
            request_data.user_agent,
            request_data.to_context(),
            api_model,
        )
    except BadSpecError as e:
        return ApiResponse(status=500, data={'error': str(e)})
    except UserError as e:
        return ApiResponse(status=400, data={'error': str(e)})
    except GenericInboundRequestFiltered:
        return ApiResponse(status=204)
    except GenericInboundValidationError as e:
        return _get_validation_error_response(e.errors)
    except GenericInboundApiError as e:
        return ApiResponse(status=500, data={'error': str(e)})
    except SubmissionError as e:
        return ApiResponse(status=400, data={
            'error': str(e),
            'form_id': e.form_id,
        })
    return ApiResponse(status=200, data=response_json)


def _get_validation_error_response(errors):
    return ApiResponse(status=400, data={
        'error': 'validation error',
        'errors': [error['message'] for error in errors],
    })


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
