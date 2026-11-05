import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory

from corehq.apps.document_templates.case_documents import CaseDocumentError
from corehq.apps.document_templates.views import render_document

DOMAIN = 'document-templates-test'
PDF = b'%PDF one'
COUCH_USER = SimpleNamespace(get_id='user-1')
DOCUMENTS = [b'%PDF one', b'%PDF two']


def _post(body):
    request = RequestFactory().post('/', body, content_type='text/plain')
    request.couch_user = SimpleNamespace(get_id='user-1')
    return inspect.unwrap(render_document)(request, DOMAIN)


def test_case_document_errors_are_returned_as_400():
    with patch(
        'corehq.apps.document_templates.views.render_case_documents', side_effect=CaseDocumentError('Nope'),
    ):
        response = _post('abc')
    assert response.status_code == 400
    assert json.loads(response.content) == {'error': 'Unable to render document.'}


def test_empty_body_is_a_400():
    response = _post('')
    assert response.status_code == 400


def test_case_ids_are_split_on_whitespace():
    with patch('corehq.apps.document_templates.views.render_case_documents', return_value=PDF) as build:
        _post('abc def  ghi')
    build.assert_called_once_with(DOMAIN, ['abc', 'def', 'ghi'])


def test_the_pdf_is_returned():
    with patch('corehq.apps.document_templates.views.render_case_documents', return_value=PDF):
        response = _post('abc')
    assert response.getvalue() == PDF
    assert response['Content-Type'] == 'application/pdf'
    assert response['Content-Disposition'] == 'inline; filename="document.pdf"'
    assert response['X-Content-Type-Options'] == 'nosniff'
