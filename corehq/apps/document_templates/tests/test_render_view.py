import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from corehq.apps.document_templates.case_documents import CaseDocumentError
from corehq.apps.document_templates.views import RenderDocumentView

DOMAIN = 'document-templates-test'
PDF = b'%PDF one'
COUCH_USER = SimpleNamespace(get_id='user-1')


def _post(body):
    request = RequestFactory().post('/', body, content_type='text/plain')
    request.couch_user = COUCH_USER
    return RenderDocumentView().post(request, DOMAIN)


class TestRenderDocumentViewErrors(SimpleTestCase):

    def test_case_document_errors_are_returned_as_400(self):
        with patch(
            'corehq.apps.document_templates.views.render_case_documents', side_effect=CaseDocumentError('Nope'),
        ):
            response = _post('abc')
        assert response.status_code == 400
        assert json.loads(response.content) == {'error': 'Nope'}

    def test_empty_body_is_a_400(self):
        response = _post('')
        assert response.status_code == 400


class TestRenderDocumentView(SimpleTestCase):

    def test_case_ids_are_split_on_whitespace(self):
        with patch('corehq.apps.document_templates.views.render_case_documents', return_value=PDF) as build:
            _post('abc def  ghi')
        build.assert_called_once_with(DOMAIN, ['abc', 'def', 'ghi'], COUCH_USER)

    def test_the_pdf_is_returned(self):
        with patch('corehq.apps.document_templates.views.render_case_documents', return_value=PDF):
            response = _post('abc')
        assert response.content == PDF
        assert response['Content-Type'] == 'application/pdf'
