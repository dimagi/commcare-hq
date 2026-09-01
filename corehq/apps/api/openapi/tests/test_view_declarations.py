"""The ``@api_docs`` decorator itself.

Only the mechanism: that it annotates a view in place and hands back the
same object. What any particular view declares through it is that view's
business -- Case API v2's declarations are checked in
``test_case_v2_docs.py``, so a failure there names the API that is wrong
rather than the decorator, which is fine.
"""

from corehq.apps.api.openapi.view_declarations import api_docs


def test_decorator_annotates_the_view_and_returns_it():
    @api_docs(
        summary='Test endpoint',
        description='A test endpoint.',
        paths=['/a/{domain}/api/test/v1/'],
    )
    def view(request, domain):
        return 'called'

    assert view(None, 'demo') == 'called'
    assert view._openapi_docs.summary == 'Test endpoint'
    assert view._openapi_docs.paths == ['/a/{domain}/api/test/v1/']
