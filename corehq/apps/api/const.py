"""Case API v2 routes and their documented paths, declared as adjacent pairs.

Each ``_URL``/``_PATH`` pair names one endpoint in two languages: the
``_URL`` is the Django regex ``urls.py`` routes, and the ``_PATH`` is the
OpenAPI-style path template the generated spec publishes for it. Neither
language can express the other -- Django cannot route a brace template like
``{case_id}``, and OpenAPI cannot publish a regex -- so the two are kept as
separate, adjacent constants rather than derived from one another.
``test_case_v2_urls.py`` pins each pair together, and pins the routed URLs
against the ones declared here.

Each triplet also carries a ``_V06_URL``: the deprecated ``v0.6/case/...``
alias that routes the same view. Those have no ``_PATH`` because they are
deliberately unpublished -- the specs describe ``case/v2/`` only, and
``test_case_v2_urls.py`` walks the documented namespace, so the aliases fall
outside it rather than being excluded by name. They live here, beside the
routes they alias, so that the deprecated spelling of an endpoint is visible
next to the current one instead of in a separate file. Removing them is two
edits: the ``_V06_`` constants here, and the four ``url()`` entries in
``urls.py``'s ``urlpatterns`` that route them -- see that module's
"To remove the scheme" note, which covers the rest of the v0.x removal.
``test_urls.py`` pins them meanwhile.
"""

CASE_LIST_URL = r'case/v2/?$'
# Trailing slash optional: https://github.com/dimagi/commcare-hq/pull/29939
CASE_V06_LIST_URL = r'v0.6/case/?$'
CASE_LIST_PATH = '/a/{domain}/api/case/v2/'

CASE_DETAIL_URL = r'case/v2/(?P<case_id>[\w\-,]+)/?$'
CASE_V06_DETAIL_URL = r'v0\.6/case/(?P<case_id>[\w\-,]+)/?$'
CASE_DETAIL_PATH = '/a/{domain}/api/case/v2/{case_id}/'

# external_id matches greedily, slashes included, as ``<path:...>`` did
CASE_EXT_URL = r'case/v2/ext/(?P<external_id>.+)/$'
CASE_V06_EXT_URL = r'v0\.6/case/ext/(?P<external_id>.+)/$'
CASE_EXT_PATH = '/a/{domain}/api/case/v2/ext/{external_id}/'

CASE_BULK_FETCH_URL = r'case/v2/bulk-fetch/$'
CASE_V06_BULK_FETCH_URL = r'v0\.6/case/bulk-fetch/$'
CASE_BULK_FETCH_PATH = '/a/{domain}/api/case/v2/bulk-fetch/'
