"""Generation of OpenAPI paths, operations and parameters for a resource."""

from dataclasses import dataclass

from tastypie.constants import ALL, ALL_WITH_RELATIONS

from corehq.apps.api.openapi import emit
from corehq.apps.api.openapi.catalogue import USER
from corehq.apps.api.openapi.declarations import (
    DEFAULT_FIELD_SCHEMAS,
    response_object,
    query_parameter,
)
from corehq.apps.api.openapi.docs import collect_docs, reject_misfiled_docs
from corehq.apps.api.openapi.examples import load_example
from corehq.apps.api.openapi.schema import field_to_schema
from corehq.apps.api.openapi.security import (
    enforces_authentication,
    required_permission,
)


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
            parameters.append(query_parameter(name))
    return parameters


def _limit_description(max_limit):
    """What ``limit`` actually does, given the resource's cap.

    ``Paginator.get_limit()`` returns ``max_limit`` when the requested limit
    is 0 or above the cap, so "0 means every record" is only true for a
    resource whose cap is falsy -- and every documented resource has one,
    since tastypie's ``ResourceOptions`` defaults it to 1000.
    """
    if not max_limit:
        return (
            'Maximum number of records to return. '
            'Use 0 to request all records.'
        )
    return (
        'Maximum number of records to return, capped at '
        f'{max_limit}. Use 0 to request that maximum.'
    )


def standard_list_parameters(resource_schema, max_limit):
    """The pagination and format parameters every list endpoint accepts."""
    parameters = [
        query_parameter(
            'limit',
            _limit_description(max_limit),
            {
                'type': 'integer',
                'default': resource_schema['default_limit'],
            },
        ),
        query_parameter(
            'offset',
            'Number of records to skip.',
            {'type': 'integer', 'default': 0},
        ),
        query_parameter(
            'format',
            'Response format.',
            {
                'type': 'string',
                'enum': ['json', 'xml'],
                'default': 'json',
            },
        ),
    ]
    ordering = resource_schema.get('ordering')
    if ordering:
        enum = [field for field in ordering]
        enum += [f'-{field}' for field in ordering]
        parameters.append(
            query_parameter(
                'order_by',
                'Field to sort by. Prefix with "-" to reverse.',
                {'type': 'string', 'enum': enum},
            )
        )
    return parameters


def object_schema(resource_schema, docs, *, use_in=None, for_list=False):
    """The schema for a single object returned by the resource.

    Properties come from two declarations that mean different things. A
    ``Docs.field_schemas`` entry overrides a declared Tastypie field's
    generated schema, and its key must name one -- ``reject_misfiled_docs()``
    rejects one that does not. A ``Docs.added_fields`` entry describes a key
    the resource puts in ``bundle.data`` outside Tastypie's field machinery
    (in a ``dehydrate()`` override, say), so there is no generated schema to
    override and the entry is used as the property's schema outright. Such
    an entry carries its own ``description``, since there is no
    ``help_text`` to hang one on.

    Which of the two an entry belongs in used to be inferred from its
    shape -- an unmatched key carrying a ``type`` was an addition, one
    without was ignored -- which made a mistyped field name either a
    phantom property or a silent no-op, depending on the typo.

    ``use_in`` is a ``{field_name: field.use_in}`` map (``build_schema()``
    does not report it, so it has to be read separately off the live
    resource's ``.fields``). A field whose ``use_in`` is ``'list'`` or
    ``'detail'`` is dropped from the schema built for the other one, the
    same way ``full_dehydrate()`` drops it from the actual response --
    see e.g. ``web-user-v1``'s ``tableau_groups`` (``use_in='detail'``),
    which must not appear in the list schema it never appears in.
    """
    declared_fields = resource_schema['fields']
    use_in = use_in or {}
    wanted = 'list' if for_list else 'detail'
    visible_fields = {
        name: info
        for name, info in declared_fields.items()
        if use_in.get(name, 'all') in ('all', wanted)
    }
    properties = {
        name: field_to_schema(info, override=_field_override(name, docs))
        for name, info in visible_fields.items()
    }
    properties.update(_added_fields(docs))
    return {'type': 'object', 'properties': properties}


def _field_override(name, docs):
    """The schema fragment merged over a declared field's generated one.

    ``DEFAULT_FIELD_SCHEMAS`` is merged first so a resource's own
    ``Docs.field_schemas`` entry still wins over it.
    """
    return {
        **DEFAULT_FIELD_SCHEMAS.get(name, {}),
        **docs.get('field_schemas', {}).get(name, {}),
    }


def _added_fields(docs, *, writable=None):
    """``Docs.added_fields``: properties outside Tastypie's declared fields.

    ``writable=True`` excludes an entry marked ``readOnly`` -- e.g.
    location-v2's ``location_type_name``, which is derived in
    ``dehydrate()`` from ``location_type_code`` and never read back out of
    a write request -- so that ``request_schema`` does not invent a
    writable property nothing in the resource's ``obj_create``/
    ``obj_update`` actually consumes.
    """
    added = {
        name: dict(schema)
        for name, schema in docs.get('added_fields', {}).items()
    }
    if writable:
        added = {
            name: schema
            for name, schema in added.items()
            if not schema.get('readOnly')
        }
    return added


def request_schema(resource_schema, docs):
    """The schema a write request accepts: the writable fields only.

    A ``Docs.added_fields`` entry (see ``object_schema()``) is applied
    here too, so a request-only field -- one a resource's ``obj_create``/
    ``obj_update`` reads from ``bundle.data`` without it being a declared
    Tastypie field, such as ``CommCareUserResource``'s ``password`` --
    can be documented at all. Without this, the convention could declare
    additions for responses but had no way to express one for requests.

    Most HQ resources hand-roll ``obj_create``/``obj_update`` and reject
    any key their own dispatch table does not recognise -- Tastypie's
    generic hydrate path (which every declared, non-readonly field would
    genuinely accept) is not what actually runs. A ``Docs.writable_fields``
    set, where present, is therefore the authority on what a write request
    accepts, restricting both declared fields and additions to exactly
    that set; a resource with no ``writable_fields`` falls back to "every
    non-readonly declared field", which is only correct for resources that
    really do use Tastypie's generic hydrate path.
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
    # ``obj_create``, which is out of scope for this pass. Case v2 is the
    # exception: its request models are ``jsonobject`` classes, so
    # ``jsonobject_schema.py`` derives ``required`` from their own
    # ``required=True`` rather than guessing at it.
    declared_fields = resource_schema['fields']
    writable_fields = docs.get('writable_fields')
    properties = {
        name: field_to_schema(info, override=_field_override(name, docs))
        for name, info in declared_fields.items()
        if not info.get('readonly')
        and (writable_fields is None or name in writable_fields)
    }
    additions = _added_fields(docs, writable=True)
    if writable_fields is not None:
        additions = {
            name: schema
            for name, schema in additions.items()
            if name in writable_fields
        }
    properties.update(additions)
    return {'type': 'object', 'properties': properties}


def _description(docs, resource):
    parts = []
    if docs.get('description'):
        parts.append(docs['description'].strip())
    permission = docs.get('permissions') or required_permission(resource)
    if permission:
        parts.append(f'Requires the `{permission}` permission.')
    return '\n\n'.join(parts)



@dataclass(frozen=True)
class _ResourceContext:
    """Everything one catalogue entry says about itself, derived once.

    Building a resource's path items needs about fifteen facts about it --
    where it is routed, what its responses look like, what its operations
    are called, whether it enforces authentication. Deriving them once and
    passing them as a unit is what lets the three blocks below be separate
    functions; passing them individually is what had
    ``_extra_operation_paths()`` taking seven positional arguments.
    """

    entry: object
    resource: object
    resource_schema: dict
    docs: dict
    name: str
    base: str
    detail: str
    detail_key: str
    path_parameters: list
    security: object
    summary: str
    description: str
    list_schema: dict
    schema: dict
    write_schema: dict


def _resource_context(entry):
    """Derive a ``_ResourceContext`` from a catalogue entry."""
    resource = entry.resource(api_name=entry.version)
    resource_schema = resource.build_schema()
    docs = collect_docs(entry.resource)
    reject_misfiled_docs(entry.resource, docs, resource_schema)

    name = resource._meta.resource_name
    base = entry.base_path()
    detail_key = resource._meta.detail_uri_name

    # A field's ``use_in`` may itself be a callable (e.g. HQ's own
    # ``UseIfRequested`` -- see corehq/apps/api/fields.py), evaluated
    # per-bundle at dehydration time. There's no bundle here to call it
    # with, and the conservative, previously-true-for-every-field
    # reading is "appears in both": treat a callable the same as 'all'
    # rather than mistakenly excluding the field from both schemas.
    use_in = {
        field_name: (field.use_in if not callable(field.use_in) else 'all')
        for field_name, field in resource.fields.items()
    }
    return _ResourceContext(
        entry=entry,
        resource=resource,
        resource_schema=resource_schema,
        docs=docs,
        name=name,
        base=base,
        detail=f'{base}{{{detail_key}}}/',
        detail_key=detail_key,
        path_parameters=(
            [] if entry.scope == USER else [emit.domain_parameter()]
        ),
        # ``None`` leaves the operation inheriting the document-wide
        # security requirement; ``[]`` is OpenAPI's explicit "this one
        # needs none".
        security=None if enforces_authentication(resource) else [],
        summary=docs.get('summary') or name.replace('_', ' ').title(),
        description=_description(docs, resource),
        # The response schema differs between the list and detail paths
        # whenever a field is ``use_in``-restricted to one or the other
        # (see ``object_schema()``). Write responses -- a POST's created
        # record, a PUT's updated one -- describe a single object, so they
        # use the detail shape even when they appear on the list path.
        list_schema=object_schema(
            resource_schema, docs, use_in=use_in, for_list=True
        ),
        schema=object_schema(
            resource_schema, docs, use_in=use_in, for_list=False
        ),
        write_schema=request_schema(resource_schema, docs),
    )


def _list_path_item(ctx):
    """The path item for a resource's list path, or None if it allows no
    method there."""
    methods = ctx.resource_schema['allowed_list_http_methods']
    if not methods:
        return None
    overrides = ctx.docs.get('list_write_responses', {})
    item = {'parameters': list(ctx.path_parameters)}
    for method in methods:
        if method == 'get':
            responses = _list_responses(ctx.list_schema)
            example = ctx.docs.get('examples', {}).get('list_response')
            if example:
                responses['200']['content']['application/json'][
                    'example'
                ] = load_example(example)
        elif method in overrides:
            responses = overrides[method]
        else:
            responses = _write_responses(
                method,
                ctx.schema,
                always_return_data=ctx.resource._meta.always_return_data,
                is_list=True,
                collection_name=ctx.resource._meta.collection_name,
            )
        operation = emit.operation(
            ctx.summary,
            f'{ctx.name}_{ctx.entry.version}_list_{method}',
            ctx.name,
            responses,
            ctx.description,
            ctx.security,
        )
        if method == 'get':
            derived = standard_list_parameters(
                ctx.resource_schema, ctx.resource._meta.max_limit
            ) + filter_parameters(ctx.resource_schema.get('filtering', {}))
            operation['parameters'] = merge_declared_parameters(
                derived, ctx.docs.get('parameters', [])
            )
        else:
            operation['requestBody'] = ctx.docs.get(
                'list_request_body'
            ) or emit.request_body(ctx.write_schema)
        item[method] = operation
    return item


def _detail_path_item(ctx):
    """The path item for a resource's detail path, or None if it ends up
    with no operations on it."""
    methods = ctx.resource_schema['allowed_detail_http_methods']
    if not methods:
        return None
    overrides = ctx.docs.get('detail_write_responses', {})
    item = {
        'parameters': list(ctx.path_parameters)
        + emit.path_parameters(
            ctx.detail, {ctx.detail_key: 'Unique identifier of the record.'}
        ),
    }
    for method in methods:
        # POST targets a single identified item, never the collection, so
        # it is never a real Tastypie operation on a detail path --
        # Tastypie's default ``allowed_methods`` lists it anyway. Every
        # path reaching this branch is a detail path (see
        # ``emit.is_detail_path``, the definition the view builder uses
        # for the same rule), so the skip is unconditional here.
        if method == 'post':
            continue
        if method == 'get':
            responses = {
                '200': response_object(
                    'The requested record.', ctx.schema
                ),
            }
        elif method in overrides:
            responses = overrides[method]
        else:
            responses = _write_responses(
                method,
                ctx.schema,
                always_return_data=ctx.resource._meta.always_return_data,
                is_list=False,
                collection_name=ctx.resource._meta.collection_name,
                put_creates_on_missing=ctx.docs.get(
                    'put_creates_on_missing', False
                ),
            )
        operation = emit.operation(
            ctx.summary,
            f'{ctx.name}_{ctx.entry.version}_detail_{method}',
            ctx.name,
            responses,
            ctx.description,
            ctx.security,
        )
        if method in ('put', 'patch'):
            operation['requestBody'] = emit.request_body(ctx.write_schema)
        item[method] = operation
    if len(item) == 1:  # nothing but 'parameters'
        return None
    return item


def resource_paths(entry):
    """OpenAPI path items for one catalogue entry."""
    ctx = _resource_context(entry)
    paths = {}
    for path, item in (
        (ctx.base, _list_path_item(ctx)),
        (ctx.detail, _detail_path_item(ctx)),
    ):
        if item is not None:
            paths[path] = item
    paths.update(_extra_operation_paths(ctx))
    return paths


def _extra_operation_paths(ctx):
    """Path items for a resource's ``prepend_urls`` endpoints.

    These are extra views a resource routes alongside its standard list
    and detail paths (e.g. ``CommCareUserResource.activate_user``) --
    Tastypie has no introspectable metadata for them the way it does for
    ``allowed_*_methods``, so a resource declares them explicitly in
    ``Docs.extra_operations`` as
    ``{'path': '{pk}/activate/', 'method': 'post', 'summary': ..., 'operation_id': ...}``.
    """
    paths = {}
    for extra in ctx.docs.get('extra_operations', []):
        full_path = f'{ctx.base}{extra["path"]}'
        method = extra['method']
        item = {
            'parameters': list(ctx.path_parameters)
            + emit.path_parameters(
                full_path,
                {ctx.detail_key: 'Unique identifier of the record.'},
            ),
        }
        operation = emit.operation(
            extra['summary'],
            f'{ctx.name}_{ctx.entry.version}_{extra["operation_id"]}',
            ctx.name,
            extra.get(
                'responses',
                {
                    '202': response_object(
                        'The request was accepted.', {'type': 'object'}
                    ),
                },
            ),
            extra.get('description') or ctx.description,
        )
        item[method] = operation
        paths[full_path] = item
    return paths


def _write_responses(
    method,
    schema,
    *,
    always_return_data,
    is_list,
    collection_name,
    put_creates_on_missing=False,
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
      is set -- regardless of the flag's effect on the update case. This
      fallback only fires when the resource's own ``obj_update`` raises
      *tastypie's* ``NotFound``; a resource whose ``obj_update`` raises
      something else on a missing record (a couch ``ResourceNotFound``,
      or a resource-specific ``BadRequest`` subclass) never reaches it,
      so the 201 alternative is only documented when the caller passes
      ``put_creates_on_missing=True`` -- established per resource by
      reading its ``obj_update``.
    - PATCH returns 202, with a body only when ``always_return_data`` is
      set.
    - DELETE always returns 204 with no body -- never a body, regardless
      of ``always_return_data``, which Tastypie's delete methods do not
      consult at all.

    This is the *generic* rule. A resource that overrides ``serialize()``,
    ``patch_list``/``patch_list_replica``, or ``post_list`` itself (e.g.
    ``CommCareUserResource``/``GroupResource``'s ``serialize()`` swapping
    a POST's full record for ``{"id": ...}``, ``patch_list_replica``'s
    bare array of ID strings, or ``SingleSignOnResource.post_list``'s own
    200-with-a-user-object) does not follow this rule for that method, and
    ``resource_paths()`` looks for a ``Docs.list_write_responses``/
    ``detail_write_responses`` override before falling back to it.
    """
    collection_schema = {
        'type': 'object',
        'properties': {collection_name: {'type': 'array', 'items': schema}},
    }

    def body_response(status, description, body_schema):
        return {status: response_object(description, body_schema)}

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
        if not is_list and put_creates_on_missing:
            # The identified record did not exist, so it was created
            # instead.
            create_body = schema if always_return_data else None
            responses.update(
                body_response('201', 'The record was created.', create_body)
            )
        return responses

    raise ValueError(f'unhandled write method: {method}')


def _list_responses(schema):
    return {
        '200': response_object(
            'A page of records.',
            {
                'type': 'object',
                'properties': {
                    'meta': {
                        '$ref': '#/components/schemas/PaginationMeta',
                    },
                    'objects': {'type': 'array', 'items': schema},
                },
            },
        ),
    }
