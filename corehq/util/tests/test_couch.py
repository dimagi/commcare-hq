from contextlib import contextmanager
from couchdbkit import ResourceNotFound
from django.http import Http404
from django.test import TestCase, SimpleTestCase
from corehq.util.couch import get_document_or_404, IterativeSaver, iter_update
from dimagi.utils.couch.database import iter_docs
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


from corehq.apps.groups.models import Group


class LoggingDB(object):
    def __init__(self):
        self.docs_saved = []
        self.num_writes = 0

    def bulk_save(self, docs):
        self.docs_saved.extend(docs)
        self.num_writes += 1
        return [{'id': 'unique_id'} for doc in docs]


class IterativeSaverSimpleTest(SimpleTestCase):
    def test_number_of_calls(self):
        db = LoggingDB()
        with IterativeSaver(db, chunksize=50) as iter_db:
            all_docs = range(105)
            for doc in all_docs:
                iter_db.save(doc)

        # the saver should have cleared out all the docs
        self.assertEqual(iter_db.to_save, [])
        # The db should have saved all the docs
        self.assertEqual(db.docs_saved, all_docs)
        # 105 docs in chunks of 50 should be 3 writes
        self.assertEqual(db.num_writes, 3)


class IterativeSaverTest(TestCase):
    def setUp(self):
        self.db = Group.get_db()
        self.groups = [
            Group(domain="TEST", name="test-{}".format(i))
            for i in range(11)
        ]

    def test_normal_usage(self):
        # use group just 'cause it's a simple model,
        # and I can't create new models within tests
        with IterativeSaver(self.db, chunksize=5) as iter_db:
            for group in self.groups:
                iter_db.save(group)
        # Make sure each of those groups has an id and is in the db
        for group in self.groups:
            self.db.get(group._id)

    def test_conflicted_doc(self):
        self.db.bulk_save(self.groups)
        old = self.groups[3]
        new = Group.get(old._id)
        new.name = "bwahahaha"
        new.save()
        self.assertEqual(old._id, new._id)
        self.assertNotEqual(old._rev, new._rev)
        # now if you try to save 'old', it should conflict
        with IterativeSaver(self.db, chunksize=5) as iter_db:
            for group in self.groups:
                iter_db.save(group)

        should_succeed = {g._id for g in self.groups if g._id != old._id}
        self.assertEqual(should_succeed, iter_db.saved_ids)

        self.assertEqual([old._id], iter_db.error_ids)
