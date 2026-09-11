"""The OpenAPI constructs both path builders emit.

``operations.py`` derives its paths from tastypie's metadata and
``view_operations.py`` reads them off a declaration, but both produce the
same OpenAPI shapes. Defining those shapes here once is what stops the two
describing the same construct differently -- an agreement that used to be
maintained by a comment in each pointing at the other.

This module knows OpenAPI. It knows nothing about tastypie, about views, or
about where a declaration came from.
"""

import re

_DOMAIN_PARAMETER = {
    'name': 'domain',
    'in': 'path',
    'required': True,
    'description': 'The project space (domain) name.',
    'schema': {'type': 'string'},
}


def domain_parameter():
    """The ``{domain}`` path parameter every domain-scoped path carries.

    A fresh dict each call. The previous module-level constant was inlined
    by reference into every path item of every document, so all of them
    shared one object and an edit to any would have rewritten the parameter
    everywhere -- including in documents already built and cached.
    """
    return {**_DOMAIN_PARAMETER, 'schema': dict(_DOMAIN_PARAMETER['schema'])}


def is_detail_path(path):
    """Whether ``path`` identifies a single record.

    A detail path ends in a path parameter -- ``/case/v2/{case_id}/``. POST
    is only ever a collection-level operation in the OpenAPI documents this
    module builds, never one on a single identified record, so no path this
    returns True for should carry a POST operation.
    """
    return path.rstrip('/').endswith('}')


def path_parameters(path, descriptions=None):
    """One parameter per ``{name}`` in ``path``, excluding ``{domain}``.

    Derived from the path itself, so a path and its parameters cannot
    disagree. ``{domain}`` is excluded because every path item already
    carries ``domain_parameter()`` -- this assumes every caller is
    domain-scoped, so a USER-scope path that templated ``{domain}`` would
    silently get an untemplated parameter. Names are matched with
    ``re.findall(r'{(\\w+)}', ...)``, so a parameter name containing a
    non-word character (e.g. ``external-id``) would not be found. Neither
    case arises in any path built today.

    ``descriptions`` maps a parameter name to its prose. A name with no
    entry -- or an empty one -- gets no ``description`` key at all, since an
    empty description renders as one in the reference pages.
    """
    descriptions = descriptions or {}
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
        if descriptions.get(name):
            parameter['description'] = descriptions[name]
        parameters.append(parameter)
    return parameters


def operation(
    summary, operation_id, tag, responses, description, security=None
):
    """The fields every operation carries, whatever path it sits on.

    ``description`` is omitted rather than set empty when there is none: an
    empty description renders as one in the reference pages.

    ``security`` of ``None`` leaves the operation inheriting the
    document-wide requirement; ``[]`` is OpenAPI's explicit "this operation
    needs no authentication", which is a different statement and must be
    emitted.
    """
    op = {
        'summary': summary,
        'operationId': operation_id,
        'tags': [tag],
        'responses': responses,
    }
    if description:
        op['description'] = description
    if security is not None:
        op['security'] = security
    return op


def request_body(schema, example=None):
    """A required JSON request body, optionally carrying an example.

    Not every operation's request is JSON -- a caller whose endpoint
    accepts something else (form fields, for example) builds its own
    request body instead of using this helper.
    """
    body = {'schema': schema}
    if example is not None:
        body['example'] = example
    return {
        'required': True,
        'content': {'application/json': body},
    }
