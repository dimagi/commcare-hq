"""OpenAPI path items for documented function-based views.

The counterpart to ``operations.py``: that module derives a resource's paths
from tastypie's metadata, and this one reads a view's paths off the
``ApiViewDocs`` its ``@api_docs`` decorator attached, because a
function-based view carries no metadata to derive from. Both emit through
``emit.py``, so the two describe the same OpenAPI constructs identically.
"""

import re

from corehq.apps.api.openapi import emit
from corehq.apps.api.openapi.declarations import response_object
from corehq.apps.api.openapi.examples import load_example


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


def operations_served(docs):
    """The ``(path, method)`` pairs this view actually publishes.

    POST targets a collection -- creating a new item, or a bulk change
    over a list -- never a single identified record, so it is skipped on
    a detail path. Shared with the tests, which need to know which
    ``request_schemas``/``examples`` keys will ever be looked up; deriving
    that twice is how a declaration goes stale without anything saying so.
    """
    return [
        (path, method)
        for path in docs.paths
        for method in docs.methods
        if not (method == 'post' and emit.is_detail_path(path))
    ]


def example_key(method):
    """The ``examples`` key holding a request example for ``method``."""
    return f'{method}_request'


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
    key = example_key(method)
    example = docs.examples.get((path, key), docs.examples.get(key))
    return schema, example


def view_paths(slug, docs):
    """OpenAPI path items for a documented function-based view."""
    paths = {}
    for path in docs.paths:
        paths[path] = {
            'parameters': [
                emit.domain_parameter(),
                *emit.path_parameters(
                    path, docs.path_parameter_descriptions
                ),
            ]
        }
    for path, method in operations_served(docs):
        response_schema = docs.response_schemas.get(
            (path, method), docs.response_schemas.get(method)
        )
        response = response_object('Success.', response_schema)
        op = emit.operation(
            docs.summary,
            f'{slug}_{_operation_id_tail(slug, path)}_{method}',
            slug,
            {'200': response},
            docs.description,
        )
        if method == 'get' and not emit.is_detail_path(path):
            op['parameters'] = docs.parameters
        schema, example = _request_schema_and_example(docs, path, method)
        if schema:
            op['requestBody'] = emit.request_body(
                schema, load_example(example) if example else None
            )
        paths[path][method] = op
    return paths
