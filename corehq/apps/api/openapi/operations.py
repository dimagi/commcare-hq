"""Generation of OpenAPI paths, operations and parameters for a resource."""

import json
from pathlib import Path

from tastypie.constants import ALL, ALL_WITH_RELATIONS

from corehq.apps.api.openapi.catalogue import USER
from corehq.apps.api.openapi.docs import collect_docs
from corehq.apps.api.openapi.schema import field_to_schema
from corehq.apps.api.openapi.security import required_permission

EXAMPLES_DIR = Path(__file__).parent / 'examples'


def load_example(relative_path):
    return json.loads((EXAMPLES_DIR / relative_path).read_text())


DOMAIN_PARAMETER = {
    'name': 'domain',
    'in': 'path',
    'required': True,
    'description': 'The project space (domain) name.',
    'schema': {'type': 'string'},
}


def filter_parameters(filtering):
    """Query parameters for a resource's ``Meta.filtering`` declaration."""
    parameters = []
    for field_name in sorted(filtering):
        filters = filtering[field_name]
        if filters in (ALL, ALL_WITH_RELATIONS):
            filters = ('exact',)
        for filter_name in filters:
            name = (
                field_name
                if filter_name == 'exact'
                else f'{field_name}__{filter_name}'
            )
            parameters.append(
                {
                    'name': name,
                    'in': 'query',
                    'required': False,
                    'schema': {'type': 'string'},
                }
            )
    return parameters


def standard_list_parameters(resource_schema):
    """The pagination and format parameters every list endpoint accepts."""
    parameters = [
        {
            'name': 'limit',
            'in': 'query',
            'required': False,
            'description': 'Maximum number of records to return. '
            'Use 0 to request all records.',
            'schema': {
                'type': 'integer',
                'default': resource_schema['default_limit'],
            },
        },
        {
            'name': 'offset',
            'in': 'query',
            'required': False,
            'description': 'Number of records to skip.',
            'schema': {'type': 'integer', 'default': 0},
        },
        {
            'name': 'format',
            'in': 'query',
            'required': False,
            'description': 'Response format.',
            'schema': {
                'type': 'string',
                'enum': ['json', 'xml'],
                'default': 'json',
            },
        },
    ]
    ordering = resource_schema.get('ordering')
    if ordering:
        enum = [field for field in ordering]
        enum += [f'-{field}' for field in ordering]
        parameters.append(
            {
                'name': 'order_by',
                'in': 'query',
                'required': False,
                'description': 'Field to sort by. Prefix with "-" to reverse.',
                'schema': {'type': 'string', 'enum': enum},
            }
        )
    return parameters


def object_schema(resource_schema, docs):
    """The schema for a single object returned by the resource."""
    field_schemas = docs.get('field_schemas', {})
    properties = {
        name: field_to_schema(info, override=field_schemas.get(name))
        for name, info in resource_schema['fields'].items()
    }
    return {'type': 'object', 'properties': properties}


def request_schema(resource_schema, docs):
    """The schema a write request accepts: the writable fields only."""
    field_schemas = docs.get('field_schemas', {})
    properties = {
        name: field_to_schema(info, override=field_schemas.get(name))
        for name, info in resource_schema['fields'].items()
        if not info.get('readonly')
    }
    return {'type': 'object', 'properties': properties}


def _description(docs, resource):
    parts = []
    if docs.get('description'):
        parts.append(docs['description'].strip())
    permission = docs.get('permissions') or required_permission(resource)
    if permission:
        parts.append(f'Requires the `{permission}` permission.')
    return '\n\n'.join(parts)


def resource_paths(entry):
    """OpenAPI path items for one catalogue entry."""
    resource = entry.resource(api_name=entry.version)
    resource_schema = resource.build_schema()
    docs = collect_docs(entry.resource)

    name = resource._meta.resource_name
    prefix = '/api' if entry.scope == USER else '/a/{domain}/api'
    base = f'{prefix}/{name}/{entry.version}/'
    detail_key = resource._meta.detail_uri_name
    detail = f'{base}{{{detail_key}}}/'

    path_parameters = [] if entry.scope == USER else [DOMAIN_PARAMETER]
    summary = docs.get('summary') or name.replace('_', ' ').title()
    description = _description(docs, resource)
    schema = object_schema(resource_schema, docs)
    write_schema = request_schema(resource_schema, docs)

    paths = {}

    list_methods = resource_schema['allowed_list_http_methods']
    if list_methods:
        item = {'parameters': list(path_parameters)}
        for method in list_methods:
            responses = _list_responses(schema)
            example = docs.get('examples', {}).get('list_response')
            if example:
                responses['200']['content']['application/json']['example'] = (
                    load_example(example)
                )
            operation = {
                'summary': summary,
                'operationId': f'{name}_{entry.version}_list_{method}',
                'tags': [name],
                'responses': responses,
            }
            if description:
                operation['description'] = description
            if method == 'get':
                operation['parameters'] = standard_list_parameters(
                    resource_schema
                ) + filter_parameters(resource_schema.get('filtering', {}))
            else:
                operation['requestBody'] = _request_body(write_schema)
            item[method] = operation
        paths[base] = item

    detail_methods = resource_schema['allowed_detail_http_methods']
    if detail_methods:
        item = {
            'parameters': list(path_parameters)
            + [
                {
                    'name': detail_key,
                    'in': 'path',
                    'required': True,
                    'description': 'Unique identifier of the record.',
                    'schema': {'type': 'string'},
                }
            ],
        }
        for method in detail_methods:
            operation = {
                'summary': summary,
                'operationId': f'{name}_{entry.version}_detail_{method}',
                'tags': [name],
                'responses': {
                    '200': {
                        'description': 'The requested record.',
                        'content': {'application/json': {'schema': schema}},
                    },
                },
            }
            if description:
                operation['description'] = description
            if method in ('put', 'patch'):
                operation['requestBody'] = _request_body(write_schema)
            item[method] = operation
        paths[detail] = item

    return paths


def _request_body(schema):
    return {
        'required': True,
        'content': {'application/json': {'schema': schema}},
    }


def _list_responses(schema):
    return {
        '200': {
            'description': 'A page of records.',
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'meta': {
                                '$ref': '#/components/schemas/PaginationMeta',
                            },
                            'objects': {'type': 'array', 'items': schema},
                        },
                    },
                },
            },
        },
    }
