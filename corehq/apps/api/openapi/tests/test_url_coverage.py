"""A resource must not route a URL its generated spec doesn't describe.

This is the gate that would have caught two defects by construction: a
resource whose ``allowed_*_methods`` publish a write Tastypie doesn't
really support (a phantom operation, rather than a missing path), and
``prepend_urls`` endpoints -- like ``CommCareUserResource``'s
``{pk}/activate/`` -- that are routed but never appeared in the spec at
all. It does not (and cannot, from URL shape alone) check that the
*methods* declared for a path are the ones Tastypie really implements;
that is covered by resource-specific tests instead.
"""

import re

import pytest

from corehq.apps.api.openapi.catalogue import USER, documented_entries
from corehq.apps.api.openapi.operations import resource_paths

# Tastypie base URLs this check does not hold a resource to:
# ``.../schema/`` is a pre-existing, separately-tracked bug (returns 500
# for most resources; see the design doc's "Pre-existing schema
# endpoints"), and ``.../set/<pks>/`` ("get_multiple") is not part of
# this generator's design at all.
_EXCLUDED_URL_NAMES = {'api_get_schema', 'api_get_multiple'}

_GROUP_RE = re.compile(r'\(\?P<(\w+)>[^)]*\)')


def _pattern_to_relative_path(pattern):
    """A Django url regex pattern, as a plain OpenAPI-style path
    fragment relative to the resource's base URL."""
    path = pattern.lstrip('^').rstrip('$')
    return _GROUP_RE.sub(r'{\1}', path)


def _routed_paths(entry):
    """Every path ``entry``'s resource actually routes, in the
    generator's ``{domain}``/``{pk}``-style path-parameter form.

    The plain list (``api_dispatch_list``) and detail
    (``api_dispatch_detail``) routes are excluded when the resource
    allows *no* methods there (an empty ``allowed_list_http_methods`` or
    ``allowed_detail_http_methods``) -- Tastypie still routes the URL,
    but every request to it 405s, so there is no operation to document
    and ``operations.resource_paths()`` deliberately omits the path
    entirely. That is a different, legitimate case from a
    ``prepend_urls`` endpoint (always some real method) or from a path
    that claims a method Tastypie doesn't implement (the phantom-write
    defect this test also guards against).
    """
    resource = entry.resource(api_name=entry.version)
    resource_schema = resource.build_schema()
    prefix = '/api' if entry.scope == USER else '/a/{domain}/api'
    base = f'{prefix}/{resource._meta.resource_name}/{entry.version}/'

    always_405 = {
        'api_dispatch_list': not resource_schema[
            'allowed_list_http_methods'
        ],
        'api_dispatch_detail': not resource_schema[
            'allowed_detail_http_methods'
        ],
    }

    paths = []
    for url in resource._get_urls():
        if url.name in _EXCLUDED_URL_NAMES:
            continue
        if always_405.get(url.name):
            continue
        relative = _pattern_to_relative_path(url.pattern.regex.pattern)
        paths.append(base if relative == '' else f'{base}{relative}')
    return paths


@pytest.mark.parametrize(
    'entry', documented_entries(), ids=lambda e: e.doc_slug
)
def test_every_routed_url_appears_in_the_generated_spec(entry):
    generated = resource_paths(entry)
    routed = _routed_paths(entry)
    missing = [path for path in routed if path not in generated]
    assert not missing, (
        f'{entry.doc_slug}: routed but undocumented path(s) {missing} -- '
        f'every URL a resource routes (including prepend_urls) must '
        f'appear in its generated spec, even if only to document that '
        f'the method it allows is a phantom (see operations.py)'
    )
