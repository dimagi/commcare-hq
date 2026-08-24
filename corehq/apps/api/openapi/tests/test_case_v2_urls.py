"""corehq.apps.api.const declares each case v2 route twice, as a Django
pattern and as the OpenAPI path the spec publishes, because neither
representation can be spelled in the other's language. The two are
adjacent so that a change to one is visible from the other. These tests
make that adjacency binding.
"""

import os

import pytest

from django.urls import get_resolver

from corehq.apps.api.const import (
    CASE_BULK_FETCH_PATH,
    CASE_BULK_FETCH_URL,
    CASE_DETAIL_PATH,
    CASE_DETAIL_URL,
    CASE_EXT_PATH,
    CASE_EXT_URL,
    CASE_LIST_PATH,
    CASE_LIST_URL,
)
from corehq.apps.api.openapi.builder import _view_docs_from_catalogue
from corehq.apps.api.openapi.tests.urlpatterns import pattern_to_relative_path

# The v0.6 aliases route to the same views but are deliberately absent
# from the published spec, so they have no documented path to compare
# against. test_urls.py pins them as routes.
PAIRS = [
    (CASE_LIST_URL, CASE_LIST_PATH),
    (CASE_DETAIL_URL, CASE_DETAIL_PATH),
    (CASE_EXT_URL, CASE_EXT_PATH),
    (CASE_BULK_FETCH_URL, CASE_BULK_FETCH_PATH),
]


@pytest.mark.parametrize('url,path', PAIRS, ids=lambda v: v[:24])
def test_each_route_matches_its_documented_path(url, path):
    assert f'/a/{{domain}}/api/{pattern_to_relative_path(url)}' == path


def _declared_paths():
    """Every path the catalogued views publish."""
    return {
        path for _, docs in _view_docs_from_catalogue() for path in docs.paths
    }


def _documented_namespace(declared):
    """The path prefix that the documented views claim, derived from
    their own paths.

    ``commonprefix`` compares character by character and can therefore
    stop mid-segment, so the result is trimmed back to the last ``/``.
    """
    prefix = os.path.commonprefix(sorted(declared))
    return prefix[: prefix.rfind('/') + 1]


def _routed_paths_in(namespace):
    """Every path the URLconf routes under ``namespace``.

    The domain-scoped API views are nested three levels deep in the
    resolver: the root ``^a/(?P<domain>...)/`` resolver contains the
    domain-specific includes, one of which is ``^api/``, whose own
    ``url_patterns`` are the actual leaf patterns.
    """
    resolver = get_resolver()
    routed = set()
    for domain_root in resolver.url_patterns:
        for api_root in getattr(domain_root, 'url_patterns', []):
            for leaf in getattr(api_root, 'url_patterns', []):
                regex = getattr(leaf.pattern, 'regex', None)
                if regex is None:
                    continue
                relative = pattern_to_relative_path(
                    regex.pattern, strict=False
                )
                path = f'/a/{{domain}}/api/{relative}'
                if path.startswith(namespace):
                    routed.add(path)
    return routed


def test_the_documented_namespace_is_the_case_v2_prefix():
    # Pins the derivation itself: A prefix trimmed one segment too far
    # would silently widen or narrow the search.
    assert _documented_namespace(_declared_paths()) == (
        '/a/{domain}/api/case/v2/'
    )


def test_the_route_walk_finds_the_known_case_v2_routes():
    namespace = _documented_namespace(_declared_paths())
    assert len(_routed_paths_in(namespace)) >= len(PAIRS)


def test_every_routed_path_under_a_documented_namespace_is_documented():
    declared = _declared_paths()
    undocumented = _routed_paths_in(_documented_namespace(declared)) - declared
    assert not undocumented, (
        f'routed but undocumented path(s): {sorted(undocumented)}'
    )
