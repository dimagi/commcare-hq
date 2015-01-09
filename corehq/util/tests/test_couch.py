from contextlib import contextmanager
from couchdbkit import ResourceNotFound
from django.http import Http404
from django.test import TestCase
from corehq.util.couch import get_document_or_404
from jsonobject.exceptions import WrappingAttributeError
from mock import Mock


class MockDb(object):
    def get(self, doc_id):
        return {'_id': doc_id, 'domain': 'ham', 'doc_type': 'MockModel'}


class MockModel(object):
    @staticmethod
    def get_db():
        return MockDb()

    @staticmethod
    def wrap(model):
        return {'wrapped': model}


@contextmanager
def mock_get_context():
    func = MockDb.get
    MockDb.get = Mock(side_effect=ResourceNotFound)
    try:
        yield
    finally:
        MockDb.get = func


@contextmanager
def mock_wrap_context():
    func = MockModel.wrap
    MockModel.wrap = Mock(side_effect=WrappingAttributeError)
    try:
        yield
    finally:
        MockModel.wrap = func


class GetDocMockTestCase(TestCase):
    """
    Tests get_document_or_404 with mocking
    """

    def test_get_document_or_404_not_found(self):
        """
        get_document_or_404 should raise 404 on ResourceNotFound
        """
        with mock_get_context():
            with self.assertRaises(Http404):
                get_document_or_404(MockModel, 'ham', '123')

    def test_get_document_or_404_bad_domain(self):
        """
        get_document_or_404 should raise 404 on incorrect domain
        """
        with self.assertRaises(Http404):
            get_document_or_404(MockModel, 'spam', '123')

    def test_get_document_or_404_wrapping_error(self):
        """
        get_document_or_404 should raise 404 on WrappingAttributeError
        """
        with mock_wrap_context():
            with self.assertRaises(Http404):
                get_document_or_404(MockModel, 'ham', '123')

    def test_get_document_or_404_success(self):
        """
        get_document_or_404 should return a wrapped model on success
        """
        doc = get_document_or_404(MockModel, 'ham', '123')
        self.assertEqual(doc, {'wrapped': {'_id': '123', 'domain': 'ham', 'doc_type': 'MockModel'}})
