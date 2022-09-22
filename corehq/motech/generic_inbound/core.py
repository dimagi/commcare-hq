from corehq.apps.hqcase.api.core import serialize_case
from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.motech.generic_inbound.exceptions import GenericInboundValidationError


def execute_generic_api(domain, couch_user, device_id, context, api_model):
    _validate_api_request(api_model, context)

    data = api_model.parsed_expression(context.root_doc, context)

    if not isinstance(data, list):
        # the bulk API always requires a list
        data = [data]

    xform, case_or_cases = handle_case_update(
        domain=domain,
        data=data,
        user=couch_user,
        device_id=device_id,
        is_creation=None,
    )

    if isinstance(case_or_cases, list):
        return {
            'form_id': xform.form_id,
            'cases': [serialize_case(case) for case in case_or_cases],
        }
    return {
        'form_id': xform.form_id,
        'case': serialize_case(case_or_cases),
    }


def _validate_api_request(api, eval_context):
    validations = api.get_validations()
    if not validations:
        return

    errors = []
    for validation in validations:
        if validation.parsed_expression(eval_context.root_doc, eval_context) is False:
            errors.append(validation.get_error_context())

    if errors:
        raise GenericInboundValidationError(errors)
