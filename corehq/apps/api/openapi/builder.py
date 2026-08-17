"""Assembly of complete OpenAPI documents for the CommCare data APIs."""

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


def build_all():
    """Every documented spec, keyed by ``doc_slug``, plus ``'bundle'``."""
    entries = documented_entries()
    documents = {
        entry.doc_slug: build_document([entry], title=_title(entry))
        for entry in entries
    }
    documents['bundle'] = build_document(entries, title='CommCare Data APIs')
    return documents
