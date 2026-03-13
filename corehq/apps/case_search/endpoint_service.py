from django.db.models import Max
from django.http import Http404

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)


def create_endpoint(domain, name, target_type, target_name, parameters, query):
    """Create a new endpoint with its first version."""
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


def save_new_version(endpoint, parameters, query):
    """Create a new version for an existing endpoint."""
    max_version = endpoint.versions.aggregate(
        max_v=Max('version_number')
    )['max_v'] or 0
    version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=max_version + 1,
        parameters=parameters,
        query=query,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return version


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


def validate_filter_spec(query, capability, case_type_name, parameters):
    """Validate a filter spec tree against capability and parameters.
    Returns a list of error strings. Empty list means valid.
    """
    errors = []
    case_type_def = None
    for ct in capability.get('case_types', []):
        if ct['name'] == case_type_name:
            case_type_def = ct
            break
    if case_type_def is None:
        errors.append(f'Unknown case type: {case_type_name}')
        return errors

    fields_by_name = {f['name']: f for f in case_type_def.get('fields', [])}
    param_names = {p['name'] for p in parameters}
    all_auto_refs = set()
    for refs in capability.get('auto_values', {}).values():
        for ref in refs:
            all_auto_refs.add(ref['ref'])
    schemas = capability.get('component_input_schemas', {})

    _validate_node(query, fields_by_name, param_names, all_auto_refs, schemas, errors)
    return errors


def _validate_node(node, fields_by_name, param_names, all_auto_refs, schemas, errors):
    node_type = node.get('type')
    if node_type in ('and', 'or'):
        for child in node.get('children', []):
            _validate_node(child, fields_by_name, param_names, all_auto_refs, schemas, errors)
    elif node_type == 'not':
        child = node.get('child')
        if child:
            _validate_node(child, fields_by_name, param_names, all_auto_refs, schemas, errors)
    elif node_type == 'component':
        _validate_component(node, fields_by_name, param_names, all_auto_refs, schemas, errors)
    else:
        errors.append(f'Unknown node type: {node_type}')


def _validate_component(node, fields_by_name, param_names, all_auto_refs, schemas, errors):
    field_name = node.get('field', '')
    component = node.get('component', '')
    inputs = node.get('inputs', {})

    field_def = fields_by_name.get(field_name)
    if field_def is None:
        errors.append(f'Unknown field: {field_name}')
        return

    if component not in field_def.get('operations', []):
        errors.append(
            f'Component "{component}" is not valid for field "{field_name}" '
            f'(type: {field_def["type"]})'
        )
        return

    schema = schemas.get(component, [])
    for slot in schema:
        slot_name = slot['name']
        if slot_name not in inputs:
            errors.append(
                f'Missing required input "{slot_name}" for component "{component}" '
                f'on field "{field_name}"'
            )
            continue
        _validate_input_value(
            inputs[slot_name], slot_name, component, field_name,
            param_names, all_auto_refs, errors,
        )


def _validate_input_value(value, slot_name, component, field_name,
                          param_names, all_auto_refs, errors):
    value_type = value.get('type')
    if value_type == 'constant':
        pass
    elif value_type == 'parameter':
        ref = value.get('ref', '')
        if ref not in param_names:
            errors.append(
                f'Unknown parameter "{ref}" in input "{slot_name}" '
                f'for component "{component}" on field "{field_name}"'
            )
    elif value_type == 'auto_value':
        ref = value.get('ref', '')
        if ref not in all_auto_refs:
            errors.append(
                f'Unknown auto-value "{ref}" in input "{slot_name}" '
                f'for component "{component}" on field "{field_name}"'
            )
    else:
        errors.append(
            f'Invalid input type "{value_type}" in input "{slot_name}" '
            f'for component "{component}" on field "{field_name}"'
        )
