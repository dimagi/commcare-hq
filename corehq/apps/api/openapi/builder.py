"""Assembly of complete OpenAPI documents for the CommCare data APIs."""

import json
import re

from corehq.apps.api.openapi.catalogue import documented_entries
from corehq.apps.api.openapi.operations import resource_paths
from corehq.apps.api.openapi.security import (
    SECURITY_REQUIREMENT,
    SECURITY_SCHEMES,
)

OPENAPI_VERSION = '3.0.3'

SERVERS = [
    {
        'url': 'https://{host}',
        'description': 'A CommCare HQ instance.',
        'variables': {
            'host': {
                'default': 'www.commcarehq.org',
                'description': 'Hostname of the CommCare HQ instance.',
            },
        },
    }
]

PAGINATION_META_SCHEMA = {
    'type': 'object',
    'description': 'Pagination metadata for a page of records.',
    'properties': {
        'limit': {'type': 'integer'},
        'offset': {'type': 'integer'},
        'total_count': {'type': 'integer'},
        'next': {'type': 'string', 'nullable': True},
        'previous': {'type': 'string', 'nullable': True},
    },
}


def _references_pagination_meta(paths):
    """Whether any operation in ``paths`` ``$ref``s ``PaginationMeta``.

    Only a resource with a list endpoint gets the paginated-list response
    that refs it (see ``operations._list_responses()``); a document made
    up entirely of detail-only or function-based-view paths never does,
    and declaring the schema there anyway is what Spectral's
    ``oas3-unused-component`` rule is catching.
    """
    needle = '#/components/schemas/PaginationMeta'
    return needle in json.dumps(paths)


def build_document(entries, *, title, tags=()):
    paths = {}
    for entry in entries:
        paths.update(resource_paths(entry))
    schemas = {}
    if _references_pagination_meta(paths):
        schemas['PaginationMeta'] = PAGINATION_META_SCHEMA
    document = {
        'openapi': OPENAPI_VERSION,
        'info': {
            'title': title,
            'version': '1.0.0',
            'description': 'CommCare data API.',
        },
        'servers': SERVERS,
        'paths': paths,
        'components': {
            'schemas': schemas,
            'securitySchemes': SECURITY_SCHEMES,
        },
        'security': SECURITY_REQUIREMENT,
    }
    if tags:
        document['tags'] = list(tags)
    return document


def _resource_tag(entry):
    """The (name, description) tag pair for a catalogue entry's resource.

    ``name`` matches the tag ``operations.resource_paths()`` attaches to
    every operation for this resource (its Tastypie ``resource_name``), so
    declaring it globally here satisfies Spectral's
    ``operation-tag-defined`` rule without inventing anything -- the
    description, when there is one, comes straight from the resource's own
    ``Docs``.
    """
    from corehq.apps.api.openapi.docs import collect_docs

    resource = entry.resource(api_name=entry.version)
    name = resource._meta.resource_name
    docs = collect_docs(entry.resource)
    description = docs.get('description') or docs.get('summary')
    return name, description


def _view_tag(docs):
    """The (name, description) tag pair for a documented function-based
    view, matching the tag ``view_paths()`` attaches to its operations."""
    return docs.doc_slug, (docs.description or docs.summary)


def _merge_tags(pairs):
    """Deduplicate ``(name, description)`` pairs into an OpenAPI ``tags``
    list, preserving first-seen order.

    The first non-empty description seen for a name wins; a later
    occurrence with no description does not blank one out (this matters
    for the bundle, where the same tag name can recur once per
    version of a resource).
    """
    tags = {}
    for name, description in pairs:
        if description and not tags.get(name):
            tags[name] = description
        else:
            tags.setdefault(name, description)
    result = []
    for name, description in tags.items():
        tag = {'name': name}
        if description:
            tag['description'] = description
        result.append(tag)
    return result


def _title(entry):
    from corehq.apps.api.openapi.docs import collect_docs

    docs = collect_docs(entry.resource)
    if docs.get('summary'):
        return docs['summary']
    return entry.doc_slug.replace('-', ' ').title()


def _path_parameters(path, descriptions):
    """Path parameters for a path template, other than ``{domain}``."""
    parameters = []
    for name in re.findall(r'{(\w+)}', path):
        if name == 'domain':
            continue
        parameter = {
            'name': name,
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
        }
        if name in descriptions:
            parameter['description'] = descriptions[name]
        parameters.append(parameter)
    return parameters


def _operation_id_tail(doc_slug, path):
    """A short, unique-per-path token to build an ``operationId`` from.

    ``doc_slug`` is ``<resource>-<version>``, and every path this view
    serves is expected to share the ``/a/{domain}/api/<resource>/
    <version>`` prefix that implies; stripping it keeps operationIds
    short while still being unique across every path of the view (unlike
    a generic "list"/"detail" label, which collides once a view serves
    more than one non-detail path, e.g. a bulk-fetch endpoint alongside
    the plain list path).
    """
    prefix = f'/a/{{domain}}/api/{doc_slug.replace("-", "/")}'
    tail = path[len(prefix) :] if path.startswith(prefix) else path
    tail = tail.strip('/').replace('{', '').replace('}', '')
    tail = re.sub(r'[^a-zA-Z0-9]+', '_', tail).strip('_')
    return tail or 'list'


def _request_schema_and_example(docs, path, method):
    """The requestBody schema and example for one path's operation.

    A ``request_schemas``/``examples`` key may be a plain method name,
    applied to every path, or a ``(path, key)`` tuple overriding that for
    one specific path -- e.g. a create/update endpoint whose list path
    accepts a single object or a bulk list, but whose detail path (the
    item is already identified by the URL) only ever accepts one object.
    """
    schema = docs.request_schemas.get(
        (path, method), docs.request_schemas.get(method)
    )
    example_key = f'{method}_request'
    example = docs.examples.get(
        (path, example_key), docs.examples.get(example_key)
    )
    return schema, example


def view_paths(docs):
    """OpenAPI path items for a documented function-based view."""
    from corehq.apps.api.openapi.operations import (
        DOMAIN_PARAMETER,
        load_example,
    )

    paths = {}
    for path in docs.paths:
        descriptions = docs.path_parameter_descriptions
        item = {
            'parameters': [
                DOMAIN_PARAMETER,
                *_path_parameters(path, descriptions),
            ]
        }
        is_detail = path.rstrip('/').endswith('}')
        for method in docs.methods:
            # POST targets the collection (creating a new item, or a bulk
            # change over a list), never a single identified item, so it
            # is never a real operation on a detail path.
            if method == 'post' and is_detail:
                continue
            response_schema = docs.response_schemas.get(
                (path, method), docs.response_schemas.get(method)
            )
            response = {'description': 'Success.'}
            if response_schema:
                response['content'] = {
                    'application/json': {'schema': response_schema},
                }
            operation = {
                'summary': docs.summary,
                'description': docs.description,
                'operationId': (
                    f'{docs.doc_slug}_{_operation_id_tail(docs.doc_slug, path)}'
                    f'_{method}'
                ),
                'tags': [docs.doc_slug],
                'responses': {'200': response},
            }
            if method == 'get' and not is_detail:
                operation['parameters'] = docs.parameters
            schema, example = _request_schema_and_example(docs, path, method)
            if schema:
                body = {'schema': schema}
                if example:
                    body['example'] = load_example(example)
                operation['requestBody'] = {
                    'required': True,
                    'content': {'application/json': body},
                }
            item[method] = operation
        paths[path] = item
    return paths


def build_all():
    """Every documented spec, keyed by ``doc_slug``, plus ``'bundle'``."""
    entries = documented_entries()
    documents = {
        entry.doc_slug: build_document(
            [entry],
            title=_title(entry),
            tags=_merge_tags([_resource_tag(entry)]),
        )
        for entry in entries
    }
    resource_tags = [_resource_tag(entry) for entry in entries]
    bundle = build_document(
        entries, title='CommCare Data APIs', tags=_merge_tags(resource_tags)
    )

    # Deferred, not because of an import cycle -- hoisting this to module
    # scope works fine, ``corehq.apps.api.urls`` never imports
    # ``builder.py`` -- but so that importing this module (e.g. for
    # ``documented_entries()`` alone) doesn't always also pull in
    # ``hqcase.views`` and, transitively, all of its Django view
    # decorators (auth, permissions, CSRF, throttling).
    from corehq.apps.hqcase import views  # noqa: F401
    from corehq.apps.api.openapi.view_adapter import VIEW_DOCS

    # More than one decorated view can share a doc_slug (e.g. Case API v2
    # is both `case_api` and the separate `case_api_bulk_fetch` view), so
    # their paths are merged into one document rather than the later view
    # overwriting the earlier one's. The merged document's title is
    # derived from the shared doc_slug rather than from whichever view's
    # `summary` happened to register first, so it doesn't depend on --
    # or misrepresent -- registration order.
    view_documents = {}
    view_tags = []
    for docs in VIEW_DOCS:
        paths = view_paths(docs)
        view_tags.append(_view_tag(docs))
        if docs.doc_slug in view_documents:
            view_documents[docs.doc_slug]['paths'].update(paths)
        else:
            title = docs.doc_slug.replace('-', ' ').title()
            document = build_document(
                [], title=title, tags=_merge_tags([_view_tag(docs)])
            )
            document['paths'] = paths
            view_documents[docs.doc_slug] = document
        bundle['paths'].update(paths)

    if view_tags:
        bundle['tags'] = _merge_tags(resource_tags + view_tags)

    documents.update(view_documents)
    documents['bundle'] = bundle
    return documents
