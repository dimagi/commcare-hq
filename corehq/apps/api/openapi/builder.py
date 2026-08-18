"""Assembly of complete OpenAPI documents for the CommCare data APIs."""

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


def build_document(entries, *, title):
    paths = {}
    for entry in entries:
        paths.update(resource_paths(entry))
    return {
        'openapi': OPENAPI_VERSION,
        'info': {
            'title': title,
            'version': '1.0.0',
            'description': 'CommCare data API.',
        },
        'servers': SERVERS,
        'paths': paths,
        'components': {
            'schemas': {'PaginationMeta': PAGINATION_META_SCHEMA},
            'securitySchemes': SECURITY_SCHEMES,
        },
        'security': SECURITY_REQUIREMENT,
    }


def _title(entry):
    from corehq.apps.api.openapi.docs import collect_docs

    docs = collect_docs(entry.resource)
    if docs.get('summary'):
        return docs['summary']
    return entry.doc_slug.replace('-', ' ').title()


def _path_parameters(path):
    """Path parameters for a path template, other than ``{domain}``."""
    return [
        {
            'name': name,
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
        }
        for name in re.findall(r'{(\w+)}', path)
        if name != 'domain'
    ]


def view_paths(docs):
    """OpenAPI path items for a documented function-based view."""
    from corehq.apps.api.openapi.operations import (
        DOMAIN_PARAMETER,
        load_example,
    )

    paths = {}
    for path in docs.paths:
        item = {'parameters': [DOMAIN_PARAMETER, *_path_parameters(path)]}
        is_detail = path.rstrip('/').endswith('}')
        for method in docs.methods:
            # POST targets the collection (creating a new item, or a bulk
            # change over a list), never a single identified item, so it
            # is never a real operation on a detail path.
            if method == 'post' and is_detail:
                continue
            operation = {
                'summary': docs.summary,
                'description': docs.description,
                'operationId': (
                    f'{docs.doc_slug}_{"detail" if is_detail else "list"}'
                    f'_{method}'
                ),
                'tags': [docs.doc_slug],
                'responses': {
                    '200': {'description': 'Success.'},
                },
            }
            if method == 'get' and not is_detail:
                operation['parameters'] = docs.parameters
            schema = docs.request_schemas.get(method)
            if schema:
                # POST accepts either a single object or a list of them
                # for bulk changes, so publish both shapes rather than
                # only the single-object one.
                if method == 'post':
                    schema = {
                        'oneOf': [schema, {'type': 'array', 'items': schema}]
                    }
                body = {'schema': schema}
                example = docs.examples.get(f'{method}_request')
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
        entry.doc_slug: build_document([entry], title=_title(entry))
        for entry in entries
    }
    bundle = build_document(entries, title='CommCare Data APIs')

    # Deferred import to avoid a cycle: ``hqcase.views`` registers its
    # ``VIEW_DOCS`` entry as a decorator side effect at import time, and
    # ``corehq.apps.api.urls`` already imports this module.
    from corehq.apps.hqcase import views  # noqa: F401
    from corehq.apps.api.openapi.view_adapter import VIEW_DOCS

    for docs in VIEW_DOCS:
        paths = view_paths(docs)
        document = build_document([], title=docs.summary)
        document['paths'] = paths
        documents[docs.doc_slug] = document
        bundle['paths'].update(paths)

    documents['bundle'] = bundle
    return documents
