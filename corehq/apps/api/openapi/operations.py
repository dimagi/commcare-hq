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


def merge_declared_parameters(parameters, declared):
    """Merge hand-declared query parameters into a derived list.

    A declared parameter whose ``name`` matches a derived one wins (it
    carries better prose); otherwise it is appended.
    """
    if not declared:
        return parameters
    by_name = {p['name']: dict(p) for p in parameters}
    order = [p['name'] for p in parameters]
    for param in declared:
        name = param['name']
        if name not in by_name:
            order.append(name)
        by_name[name] = param
    return [by_name[name] for name in order]


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
    """The schema for a single object returned by the resource.

    A ``Docs.field_schemas`` entry normally overrides a declared Tastypie
    field's generated schema. If its key does not match any declared
    field *and* it declares a ``type``, it is instead treated as an
    *addition*: the resource adds this key to ``bundle.data`` outside of
    Tastypie's field machinery (for example in a ``dehydrate()``
    override), so there is no generated schema to override and the
    entry's value is used as the property's schema outright. Such an
    entry may carry a ``description``, the same exception already
    granted to ``resource_uri``, for the same reason: there is no
    ``help_text`` to hang it on.

    An unmatched entry with no ``type`` is not treated as an addition —
    for example, ``resource_uri``'s description-only override is
    inherited by every subclass's ``Docs``, including ones (like
    ``Meta.include_resource_uri = False``) that do not actually have a
    ``resource_uri`` field. Requiring ``type`` for additions keeps that
    inherited, no-longer-applicable override from being invented as a
    phantom property.
    """
    field_schemas = docs.get('field_schemas', {})
    declared_fields = resource_schema['fields']
    properties = {
        name: field_to_schema(info, override=field_schemas.get(name))
        for name, info in declared_fields.items()
    }
    properties.update(_field_schema_additions(field_schemas, declared_fields))
    return {'type': 'object', 'properties': properties}


def _field_schema_additions(field_schemas, declared_fields, *, writable=None):
    """``Docs.field_schemas`` entries that add a property outside of
    Tastypie's declared fields (see ``object_schema()``'s docstring for
    the ``type``-required rule that distinguishes an addition from a
    stale override).

    ``writable=True`` additionally excludes an addition explicitly
    marked ``readOnly`` -- e.g. location-v2's ``location_type_name``,
    which is derived in ``dehydrate()`` from ``location_type_code`` and
    never read back out of a write request -- so that ``request_schema``
    does not invent a writable property nothing in the resource's
    ``obj_create``/``obj_update`` actually consumes.
    """
    additions = {
        name: dict(schema)
        for name, schema in field_schemas.items()
        if name not in declared_fields and 'type' in schema
    }
    if writable:
        additions = {
            name: schema
            for name, schema in additions.items()
            if not schema.get('readOnly')
        }
    return additions


def request_schema(resource_schema, docs):
    """The schema a write request accepts: the writable fields only.

    A ``field_schemas`` addition (see ``object_schema()``) is applied
    here too, so a request-only field -- one a resource's ``obj_create``/
    ``obj_update`` reads from ``bundle.data`` without it being a declared
    Tastypie field, such as ``CommCareUserResource``'s ``password`` --
    can be documented at all. Without this, the convention could declare
    additions for responses but had no way to express one for requests.
    """
    # NOTE: Tastypie's per-field ``blank`` metadata is *not* used here to
    # derive ``required``, even though it looks like the obvious source.
    # ``blank`` defaults to ``False`` on every field unless a resource
    # explicitly opts in to ``blank=True`` -- and none of the documented
    # resources with a custom ``obj_create``/``obj_update`` (which is
    # all of them; none use Tastypie's generic hydrate/validation path)
    # do. Trying it here produced e.g. ``email``, ``phone_numbers`` and
    # ``user_data`` as "required" for ``CommCareUserResource`` POST,
    # which is simply wrong -- only ``username`` and ``password`` are.
    # Getting this right would mean reading each resource's hand-written
    # ``obj_create``, which is out of scope for this pass; see the
    # openapi generation report for case-v2, where ``required`` *is*
    # reliably derived, via ``jsonobject``'s own ``required=True``.
    field_schemas = docs.get('field_schemas', {})
    declared_fields = resource_schema['fields']
    properties = {
        name: field_to_schema(info, override=field_schemas.get(name))
        for name, info in declared_fields.items()
        if not info.get('readonly')
    }
    properties.update(
        _field_schema_additions(field_schemas, declared_fields, writable=True)
    )
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

    always_return_data = resource._meta.always_return_data
    collection_name = resource._meta.collection_name

    list_methods = resource_schema['allowed_list_http_methods']
    if list_methods:
        item = {'parameters': list(path_parameters)}
        for method in list_methods:
            if method == 'get':
                responses = _list_responses(schema)
                example = docs.get('examples', {}).get('list_response')
                if example:
                    responses['200']['content']['application/json'][
                        'example'
                    ] = load_example(example)
            else:
                responses = _write_responses(
                    method,
                    schema,
                    always_return_data=always_return_data,
                    is_list=True,
                    collection_name=collection_name,
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
                derived = standard_list_parameters(
                    resource_schema
                ) + filter_parameters(resource_schema.get('filtering', {}))
                operation['parameters'] = merge_declared_parameters(
                    derived, docs.get('parameters', [])
                )
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
            # POST targets a single identified item, never the
            # collection, so it is never a real Tastypie operation on a
            # detail path -- Tastypie's default ``allowed_methods`` lists
            # it anyway. ``builder.view_paths()`` makes the equivalent
            # skip for function-based views; this keeps the two paths in
            # agreement.
            if method == 'post':
                continue
            if method == 'get':
                responses = {
                    '200': {
                        'description': 'The requested record.',
                        'content': {
                            'application/json': {'schema': schema}
                        },
                    },
                }
            else:
                responses = _write_responses(
                    method,
                    schema,
                    always_return_data=always_return_data,
                    is_list=False,
                    collection_name=collection_name,
                )
            operation = {
                'summary': summary,
                'operationId': f'{name}_{entry.version}_detail_{method}',
                'tags': [name],
                'responses': responses,
            }
            if description:
                operation['description'] = description
            if method in ('put', 'patch'):
                operation['requestBody'] = _request_body(write_schema)
            item[method] = operation
        if len(item) > 1:  # more than just 'parameters'
            paths[detail] = item

    paths.update(_extra_operation_paths(entry, docs, base, detail_key,
                                        path_parameters, name, description))

    return paths


def _extra_operation_paths(
    entry, docs, base, detail_key, path_parameters, name, description
):
    """Path items for a resource's ``prepend_urls`` endpoints.

    These are extra views a resource routes alongside its standard list
    and detail paths (e.g. ``CommCareUserResource.activate_user``) --
    Tastypie has no introspectable metadata for them the way it does for
    ``allowed_*_methods``, so a resource declares them explicitly in
    ``Docs.extra_operations`` as
    ``{'path': '<pk>/activate/', 'method': 'post', 'summary': ..., 'operation_id': ...}``.
    """
    paths = {}
    for extra in docs.get('extra_operations', []):
        full_path = f'{base}{extra["path"]}'
        method = extra['method']
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
        operation = {
            'summary': extra['summary'],
            'operationId': (
                f'{name}_{entry.version}_{extra["operation_id"]}'
            ),
            'tags': [name],
            'responses': extra.get(
                'responses',
                {
                    '202': {
                        'description': 'The request was accepted.',
                        'content': {
                            'application/json': {
                                'schema': {'type': 'object'},
                            },
                        },
                    },
                },
            ),
        }
        op_description = extra.get('description') or description
        if op_description:
            operation['description'] = op_description
        item[method] = operation
        paths[full_path] = item
    return paths


def _request_body(schema):
    return {
        'required': True,
        'content': {'application/json': {'schema': schema}},
    }


def _write_responses(
    method, schema, *, always_return_data, is_list, collection_name
):
    """The response(s) Tastypie actually returns for a write method.

    Read from ``tastypie.resources.Resource``'s ``post_list``,
    ``put_list``, ``put_detail``, ``patch_list``/``patch_detail`` and
    ``delete_list``/``delete_detail``:

    - POST (list only; never a real operation on a detail path -- see
      the caller) creates a record and returns 201, with a body (the
      created record) only when ``Meta.always_return_data`` is set;
      otherwise the body is empty and the record's URI comes back in a
      ``Location`` header instead.
    - PUT normally updates: 204 with no body by default, or 200 with the
      updated record (or records, for the list path) when
      ``always_return_data`` is set. On a detail path, if the identified
      record does not exist, Tastypie falls back to creating it instead,
      which returns 201 -- with a body only when ``always_return_data``
      is set -- regardless of the flag's effect on the update case. Both
      outcomes are documented as alternate responses for PUT detail.
    - PATCH returns 202, with a body only when ``always_return_data`` is
      set.
    - DELETE always returns 204 with no body -- never a body, regardless
      of ``always_return_data``, which Tastypie's delete methods do not
      consult at all.
    """
    collection_schema = {
        'type': 'object',
        'properties': {collection_name: {'type': 'array', 'items': schema}},
    }

    def body_response(status, description, body_schema):
        response = {'description': description}
        if body_schema is not None:
            response['content'] = {
                'application/json': {'schema': body_schema}
            }
        return {status: response}

    if method == 'post':
        body = schema if always_return_data else None
        return body_response('201', 'The created record.', body)

    if method == 'delete':
        return body_response('204', 'The record was deleted.', None)

    if method == 'patch':
        body = schema if always_return_data else None
        return body_response('202', 'The update was accepted.', body)

    if method == 'put':
        updated_schema = collection_schema if is_list else schema
        update_body = updated_schema if always_return_data else None
        responses = body_response(
            '200' if always_return_data else '204',
            'The record was updated.',
            update_body,
        )
        if not is_list:
            # The identified record did not exist, so it was created
            # instead.
            create_body = schema if always_return_data else None
            responses.update(
                body_response('201', 'The record was created.', create_body)
            )
        return responses

    raise AssertionError(f'unhandled write method: {method}')


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
