"""Case API routes and their documented paths.

Each endpoint is declared as a triplet: ``_URL`` is the Django regex
``urls.py`` routes, ``_PATH`` is the OpenAPI-style path template the
generated spec publishes for it, and ``_V06_URL`` is the deprecated
``v0.6/case/...`` alias that routes the same view. ``_URL`` and
``_PATH`` are kept as separate, adjacent constants because neither
language can express the other -- Django cannot route a brace template
like ``{case_id}``, and OpenAPI cannot publish a regex. ``_V06_URL``
has no ``_PATH`` because it's deliberately unpublished: the specs
describe ``case/v2/`` only.

Removing a ``_V06_URL`` is two edits: the constant here, and the
matching ``url()`` entry in ``urls.py``'s ``urlpatterns`` -- see that
module's "To remove the scheme" note, which covers the rest of the v0.x
removal. ``test_case_v2_urls.py`` pins the ``_URL``/``_PATH`` pairs and
the routed URLs against the ones declared here; ``test_urls.py`` pins
the ``_V06_URL`` aliases.
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
