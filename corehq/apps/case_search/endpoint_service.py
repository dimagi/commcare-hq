from django.db import transaction
from django.db.models import Max
from django.http import Http404

from corehq.apps.case_search.endpoint_capability import (
    COMPONENT_INPUT_SCHEMAS,
    get_capability,
)
from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)


class FilterSpecValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f'Validation errors: {errors}')


@transaction.atomic
def create_endpoint(domain, name, target_type, target_name, parameters, query):
    """Create a new endpoint with its first version."""
    capability = get_capability(domain)
    errors = validate_filter_spec(query, parameters, target_name, capability)
    if errors:
        raise FilterSpecValidationError(errors)
    endpoint = CaseSearchEndpoint.objects.create(
        domain=domain,
        name=name,
        target_type=target_type,
        target_name=target_name,
    )
    version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=1,
        parameters=parameters,
        query=query,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return endpoint


@transaction.atomic
def save_new_version(endpoint, parameters, query):
    """Create a new version for an existing endpoint."""
    capability = get_capability(endpoint.domain)
    errors = validate_filter_spec(
        query, parameters, endpoint.target_name, capability
    )
    if errors:
        raise FilterSpecValidationError(errors)
    max_version = (
        endpoint.versions.aggregate(max_v=Max('version_number'))['max_v'] or 0
    )
    version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=max_version + 1,
        parameters=parameters,
        query=query,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return version


def validate_filter_spec(spec, parameters, case_type_name, capability):
    """Validate a filter spec against capability metadata.

    Returns a list of error messages (empty = valid).
    """
    errors = []
    param_names = {p['name'] for p in parameters}
    auto_value_refs = {
        auto_value['ref']
        for avs in capability.get('auto_values', {}).values()
        for auto_value in avs
    }
    case_type = next(
        (
            case_type
            for case_type in capability.get('case_types', [])
            if case_type['name'] == case_type_name
        ),
        None,
    )
    fields_by_name = (
        {field['name']: field for field in case_type['fields']}
        if case_type
        else {}
    )

    _validate_node(spec, fields_by_name, param_names, auto_value_refs, errors)
    return errors


def _validate_node(node, fields_by_name, param_names, auto_value_refs, errors):
    node_type = node.get('type')

    if node_type in ('and', 'or'):
        for child in node.get('children', []):
            _validate_node(
                child, fields_by_name, param_names, auto_value_refs, errors
            )
    elif node_type == 'not':
        child = node.get('child')
        if child:
            _validate_node(
                child, fields_by_name, param_names, auto_value_refs, errors
            )
        else:
            errors.append("'not' node must have a 'child'")
    elif node_type == 'component':
        _validate_component(
            node, fields_by_name, param_names, auto_value_refs, errors
        )
    else:
        errors.append(
            f"Invalid node type: '{node_type}'. Expected 'and', 'or', 'not', or 'component'."
        )


def _validate_component(
    node, fields_by_name, param_names, auto_value_refs, errors
):
    field_name = node.get('field', '')
    component_name = node.get('component', '')
    inputs = node.get('inputs', {})

    field = fields_by_name.get(field_name)
    if not field:
        errors.append(f"Unknown field: '{field_name}'")
        return

    if component_name not in field.get('operations', []):
        errors.append(
            f"'{component_name}' is not a valid operation for field '{field_name}' "
            f'(type: {field["type"]})'
        )
        return

    schema = COMPONENT_INPUT_SCHEMAS.get(component_name, [])
    for slot in schema:
        slot_name = slot['name']
        if slot_name not in inputs:
            errors.append(
                f"Missing required input '{slot_name}' for component '{component_name}'"
            )
            continue
        _validate_input_value(
            inputs[slot_name], slot_name, param_names, auto_value_refs, errors
        )


def _validate_input_value(
    value, slot_name, param_names, auto_value_refs, errors
):
    value_type = value.get('type')
    if value_type == 'constant':
        pass  # any value accepted
    elif value_type == 'parameter':
        ref = value.get('ref', '')
        if ref not in param_names:
            errors.append(
                f"Parameter '{ref}' referenced in '{slot_name}' is not defined"
            )
    elif value_type == 'auto_value':
        ref = value.get('ref', '')
        if ref not in auto_value_refs:
            errors.append(f"Unknown auto value '{ref}' in '{slot_name}'")
    else:
        errors.append(f"Invalid input type '{value_type}' in '{slot_name}'")


def list_endpoints(domain):
    """Return active endpoints for a domain."""
    return CaseSearchEndpoint.objects.filter(
        domain=domain,
        is_active=True,
    ).select_related('current_version')


def get_endpoint(domain, endpoint_id):
    """Return a single endpoint, raising Http404 if not found or wrong domain."""
    try:
        return CaseSearchEndpoint.objects.select_related(
            'current_version'
        ).get(
            pk=endpoint_id,
            domain=domain,
            is_active=True,
        )
    except CaseSearchEndpoint.DoesNotExist:
        raise Http404


def get_version(endpoint, version_number):
    """Return a specific version, raising Http404 if not found."""
    try:
        return endpoint.versions.get(version_number=version_number)
    except CaseSearchEndpointVersion.DoesNotExist:
        raise Http404


def deactivate_endpoint(endpoint):
    """Soft-delete an endpoint."""
    endpoint.is_active = False
    endpoint.save(update_fields=['is_active'])
