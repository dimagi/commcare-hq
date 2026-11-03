import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from soil import DownloadBase

from corehq.apps.document_templates.case_documents import CaseDocumentError
from corehq.apps.document_templates.views import RenderDocumentView

DOMAIN = 'document-templates-test'
DOCUMENTS = ['<p>one</p>', '<p>two</p>']


def _post(body):
    request = RequestFactory().post('/', body, content_type='text/plain')
    request.couch_user = SimpleNamespace(get_id='user-1')
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


class TestRenderDocumentView(TestCase):

    def test_case_ids_are_split_on_whitespace(self):
        with patch('corehq.apps.document_templates.views.render_case_documents', return_value=DOCUMENTS) as build:
            _post('abc def  ghi')
        build.assert_called_once_with(DOMAIN, ['abc', 'def', 'ghi'])

    def test_the_first_document_is_stored_for_the_requesting_user_only(self):
        with patch('corehq.apps.document_templates.views.render_case_documents', return_value=DOCUMENTS):
            response = _post('abc')
        url = json.loads(response.content)['url']
        assert url.endswith('?get_file')
        download = DownloadBase.get(url.rsplit('/', 1)[1].removesuffix('?get_file'))
        assert download.owner_ids == ['user-1']
        assert download.content_type == 'text/html'
        assert b''.join(download.toHttpResponse().streaming_content) == b'<p>one</p>'
