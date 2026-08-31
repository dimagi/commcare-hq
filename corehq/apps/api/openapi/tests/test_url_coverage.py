"""A resource must not route a URL its generated spec doesn't describe,
and must not claim a write method it cannot actually perform.

Two checks:

- ``test_every_routed_url_appears_in_the_generated_spec``: every path a
  resource's real ``_get_urls()`` routes (``prepend_urls`` included) must
  appear in its generated spec.
- ``test_every_allowed_write_method_is_actually_implemented``: for every
  write method a resource's ``Meta`` claims to allow, the resource must
  actually be able to perform it -- not raise ``NotImplementedError``
  (``tastypie.resources.Resource``'s default ``obj_create``/
  ``obj_update``/``obj_delete``) or unconditionally raise ``Unauthorized``
  (a ``ModelResource`` stuck on the default ``ReadOnlyAuthorization``).
  This is the one that actually catches the phantom-write defect: the
  path-coverage check above compares path *templates*, and Tastypie
  routes the same list/detail URL regardless of which methods
  ``Meta.allowed_*_methods`` allows there, so a resource that claims a
  write method it cannot perform still routes an unchanged URL and would
  pass the path check alone.
"""

import re

import pytest
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.resources import ModelResource
from tastypie.resources import Resource as TastypieResource

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


# The HTTP-verb entry point Tastypie's dispatch calls for each write
# method, keyed by (method, is_list). A resource may bypass obj_create/
# obj_update/obj_delete entirely by overriding one of these directly
# (e.g. SingleSignOnResource.post_list, or GroupResource/location-v2's
# own patch_list -> patch_list_replica()), which is a legitimate, fully
# custom implementation this check should trust rather than second-guess.
_ENTRY_POINT_FOR_METHOD = {
    ('post', True): 'post_list',
    ('put', True): 'put_list',
    ('put', False): 'put_detail',
    ('patch', True): 'patch_list',
    ('patch', False): 'patch_detail',
    ('delete', True): 'delete_list',
    ('delete', False): 'delete_detail',
}
# obj_create/obj_update/obj_delete all raise NotImplementedError on plain
# Resource unless overridden.
_HOOK_FOR_METHOD = {
    'post': 'obj_create',
    'put': 'obj_update',
    'patch': 'obj_update',
    'delete': 'obj_delete',
}
# The Authorization method ModelResource's generic hook calls into (see
# save()/obj_delete() in tastypie.resources), which raises Unauthorized
# if it's the default ReadOnlyAuthorization's version -- that denies
# unconditionally, regardless of who's asking.
_AUTH_METHOD_FOR_HOOK = {
    'obj_create': 'create_detail',
    'obj_update': 'update_detail',
    'obj_delete': 'delete_detail',
}


def _write_method_is_implemented(resource, method, is_list):
    """Whether ``resource`` can actually perform ``method`` (post, put,
    patch or delete) on the list or detail path, as opposed to merely
    being *routed* to accept it.

    First checks whether the resource's own class overrides the
    HTTP-verb entry point itself (``post_list``, ``patch_detail``, and
    so on) -- if so, that's a fully custom implementation and trusted
    outright, the same way a hand-written ``obj_create`` is. Otherwise,
    falls through to the two ways a resource fails this despite
    Tastypie routing the request to it:

    - The hook (``obj_create``/``obj_update``/``obj_delete``) was never
      overridden, so it's still ``tastypie.resources.Resource``'s
      version, which unconditionally raises ``NotImplementedError``
      (fixture-v1, user-domains-v1's actual bug).
    - The hook *is* overridden, but only by inheriting
      ``ModelResource``'s generic ORM implementation, which calls the
      corresponding ``Authorization`` method -- and that method is still
      ``ReadOnlyAuthorization``'s version, which unconditionally raises
      ``Unauthorized`` (location-type-v1's actual bug).

    Verifying an implementation actually works end to end is what the
    (separate, narrower) contract/live-request tests are for, not a
    structural check like this one.
    """
    entry_name = _ENTRY_POINT_FOR_METHOD[(method, is_list)]
    entry = getattr(type(resource), entry_name, None)
    generic_entries = {
        getattr(TastypieResource, entry_name, None),
        getattr(ModelResource, entry_name, None),
    }
    if entry is not None and entry not in generic_entries:
        return True

    hook_name = _HOOK_FOR_METHOD[method]
    hook = getattr(type(resource), hook_name)
    if hook is getattr(TastypieResource, hook_name):
        return False
    if hook is getattr(ModelResource, hook_name):
        auth_method_name = _AUTH_METHOD_FOR_HOOK[hook_name]
        authorization = resource._meta.authorization
        auth_method = getattr(type(authorization), auth_method_name, None)
        if auth_method is getattr(ReadOnlyAuthorization, auth_method_name):
            return False
    return True


@pytest.mark.parametrize(
    'entry', documented_entries(), ids=lambda e: e.doc_slug
)
def test_every_allowed_write_method_is_actually_implemented(entry):
    resource = entry.resource(api_name=entry.version)
    resource_schema = resource.build_schema()
    unimplemented = []
    for method in resource_schema['allowed_list_http_methods']:
        if method != 'get' and not _write_method_is_implemented(
            resource, method, is_list=True
        ):
            unimplemented.append(f'list {method}')
    for method in resource_schema['allowed_detail_http_methods']:
        # POST on a detail path is never real (see operations.py); the
        # gate above already establishes that independently of this one.
        if method not in ('get', 'post') and not _write_method_is_implemented(
            resource, method, is_list=False
        ):
            unimplemented.append(f'detail {method}')
    assert not unimplemented, (
        f'{entry.doc_slug} allows {unimplemented} in Meta, but the '
        f'resource cannot actually perform it (unoverridden obj_create/'
        f'obj_update/obj_delete, or a ModelResource stuck on '
        f'ReadOnlyAuthorization) -- this is the phantom-write defect'
    )
