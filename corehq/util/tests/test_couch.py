from contextlib import contextmanager
from couchdbkit import ResourceNotFound
from django.http import Http404
from django.test import TestCase, SimpleTestCase
from corehq.apps.groups.models import Group
from jsonobject.exceptions import WrappingAttributeError
from mock import Mock

from ..couch import (get_document_or_404, IterDB, iter_update, IterUpdateError,
        DocUpdate)


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


class TestLoggingDB(object):
    def __init__(self):
        self.docs_saved = []
        self.num_writes = 0

    def bulk_save(self, docs):
        self.docs_saved.extend(docs)
        self.num_writes += 1
        return [{'id': 'unique_id'} for doc in docs]


class IterDBSimpleTest(SimpleTestCase):
    def test_number_of_calls(self):
        db = TestLoggingDB()
        with IterDB(db, chunksize=50) as iter_db:
            all_docs = range(105)
            for doc in all_docs:
                iter_db.save(doc)

        # the saver should have cleared out all the docs
        self.assertEqual(iter_db.to_save, [])
        # The db should have saved all the docs
        self.assertEqual(db.docs_saved, all_docs)
        # 105 docs in chunks of 50 should be 3 writes
        self.assertEqual(db.num_writes, 3)


class IterDBTest(TestCase):
    def setUp(self):
        self.domain = "TEST"
        # use Group just 'cause it's a simple model,
        # and I can't create new models within tests
        self.db = Group.get_db()
        self.groups = []
        for i in range(11):
            group = Group(domain=self.domain, name="test{}".format(i), index=i)
            group.save()
            self.groups.append(group)

    def tearDown(self):
        for group in Group.by_domain(self.domain):
            group.delete()

    def test_normal_usage(self):
        with IterDB(self.db, chunksize=5) as iter_db:
            for group in self.groups:
                group['test_property'] = True
                iter_db.save(group)
        for group in self.groups:
            new = self.db.get(group._id)
            self.assertTrue(new.get('test_property', False))

    def test_conflicted_doc(self):
        old = self.groups[3]
        new = Group.get(old._id)
        new.name = "bwahahaha"
        new.save()
        self.assertEqual(old._id, new._id)
        self.assertNotEqual(old._rev, new._rev)
        # now if you try to save 'old', it should conflict
        with IterDB(self.db, chunksize=5) as iter_db:
            for group in self.groups:
                iter_db.save(group)

        should_succeed = {g._id for g in self.groups if g._id != old._id}
        self.assertEqual(should_succeed, iter_db.saved_ids)

        self.assertEqual({old._id}, iter_db.error_ids)

    def test_delete(self):
        with IterDB(self.db, chunksize=5) as iter_db:
            deleted_groups = set()
            for group in self.groups[:4]:
                deleted_groups.add(group._id)
                iter_db.delete(group)

            saved_groups = set()
            for group in self.groups[4:]:
                saved_groups.add(group._id)
                iter_db.save(group)

        self.assertEqual(deleted_groups, iter_db.deleted_ids)
        self.assertEqual(saved_groups, iter_db.saved_ids)
        for group_id in deleted_groups:
            self.assertRaises(ResourceNotFound, self.db.get, group_id)

    def test_iter_update(self):
        def desired_action(group):
            i = group['index']
            if i == 1:
                return 'DELETE'
            elif i % 2 == 0:
                return 'UPDATE'
            else:
                return 'IGNORE'

        def mark_cool(group):
            action = desired_action(group)
            if action == 'UPDATE':
                group['is_cool'] = True
                return DocUpdate(group)
            elif action == 'DELETE':
                return DocUpdate(group, delete=True)

        ids = [g._id for g in self.groups] + ['NOT_REAL_ID']
        res = iter_update(self.db, mark_cool, ids)
        self.assertEqual(res.not_found_ids, {'NOT_REAL_ID'})
        for result_ids, action in [
            (res.ignored_ids, 'IGNORE'),
            (res.deleted_ids, 'DELETE'),
            (res.updated_ids, 'UPDATE'),
        ]:
            self.assertEqual(
                result_ids,
                {g._id for g in self.groups if desired_action(g) == action}
            )

    def test_iter_update_no_actual_changes(self):
        ids = [g._id for g in self.groups]
        # tell iter_update to save the docs, but don't actually make changes
        res = iter_update(self.db, lambda doc: DocUpdate(doc), ids)
        self.assertEqual(res.ignored_ids, set(ids))

    def test_iter_update_bad_return(self):
        def update_fn(group):
            return {'not_an_instance': 'of DocUpdate'}
        ids = [g._id for g in self.groups]
        with self.assertRaises(IterUpdateError):
            iter_update(self.db, update_fn, ids)

    def test_no_retries(self):
        visited_ids = set()  # Only fail the first time

        def conflict_evens(group):
            if group['index'] % 2 == 0 and group['_id'] not in visited_ids:
                group['_rev'] = group['_rev'] + 'bad'
                visited_ids.add(group['_id'])
            return DocUpdate(group)

        ids = [g._id for g in self.groups]
        error_ids = {g._id for g in self.groups if g.index % 2 == 0}
        try:
            iter_update(self.db, conflict_evens, ids, max_retries=0)
        except IterUpdateError as e:
            self.assertEqual(e.results.error_ids, error_ids)
        else:
            assert False, "iter_update did now throw an IterUpdateError"
