import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory

from corehq.apps.document_templates.case_documents import CaseDocumentError, Failure
from corehq.apps.document_templates.views import render_document

DOMAIN = 'document-templates-test'
PDF = b'%PDF one'
RENDER = 'corehq.apps.document_templates.views.render_case_documents'
COUCH_USER = SimpleNamespace(get_id='user-1')


def _post(body):
    request = RequestFactory().post('/', body, content_type='text/plain')
    request.couch_user = COUCH_USER
    return inspect.unwrap(render_document)(request, DOMAIN)


def test_request_errors_are_returned_as_400():
    with patch(RENDER, side_effect=CaseDocumentError('Nope')):
        response = _post('abc')
    assert response.status_code == 400
    assert json.loads(response.content) == {'error': 'Nope', 'failed': []}


def test_failed_cases_are_returned_as_400():
    failures = [Failure('abc', '', 'Case not found'), Failure('def', 'Bob', 'body: x is undefined')]
    with patch(RENDER, side_effect=CaseDocumentError('2 of 2 cases cannot be rendered', failures)):
        response = _post('abc def')
    assert response.status_code == 400
    assert json.loads(response.content) == {
        'error': '2 of 2 cases cannot be rendered',
        'failed': [
            {'case_id': 'abc', 'name': '', 'reason': 'Case not found'},
            {'case_id': 'def', 'name': 'Bob', 'reason': 'body: x is undefined'},
        ],
    }


def test_empty_body_is_a_400():
    response = _post('')
    assert response.status_code == 400


def test_case_ids_are_split_on_whitespace():
    with patch(RENDER, return_value=PDF) as build:
        _post('abc def  ghi')
    build.assert_called_once_with(DOMAIN, ['abc', 'def', 'ghi'], COUCH_USER)


def test_the_pdf_is_returned():
    with patch(RENDER, return_value=PDF):
        response = _post('abc')
    assert response.getvalue() == PDF
    assert response['Content-Type'] == 'application/pdf'
    assert response['Content-Disposition'] == 'inline; filename="document.pdf"'
    assert response['X-Content-Type-Options'] == 'nosniff'
