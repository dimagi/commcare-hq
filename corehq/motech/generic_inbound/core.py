from django.utils.translation import gettext as _

from corehq.apps.hqcase.api.core import serialize_case
from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.motech.generic_inbound.exceptions import (
    GenericInboundApiError,
    GenericInboundRequestFiltered,
    GenericInboundValidationError,
)


def execute_generic_api(domain, couch_user, device_id, context, api_model):
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
