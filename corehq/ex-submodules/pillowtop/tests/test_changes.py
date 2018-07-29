from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import SimpleTestCase
from pillowtop.dao.mock import MockDocumentStore
from pillowtop.feed.couch import change_from_couch_row
from pillowtop.feed.interface import Change
from pillowtop.feed.mock import RandomChangeFeed, MockChangeFeed
from six.moves import range


class TestCouchChange(SimpleTestCase):

    def test_convert_to_and_from_couch_row(self):
        couch_row = {
            'id': 'an-id',
            'doc': {'a': 'document'},
            'seq': '21',
            'deleted': False
        }
        ways_to_make_change_object = [
            change_from_couch_row(couch_row),
        ]
        for change in ways_to_make_change_object:
            self.assertTrue(isinstance(change, Change))
            self.assertEqual('an-id', change.id)
            self.assertEqual(couch_row['doc'], change.document)
            self.assertEqual('21', change.sequence_id)
            self.assertEqual(False, change.deleted)
            for key in couch_row:
                self.assertEqual(couch_row[key], change[key])

    def test_set_attr_id(self):
        change = Change(id='first-id', sequence_id='')
        self.assertEqual('first-id', change.id)
        change.id = 'new-id'
        self.assertEqual('new-id', change.id)
        self.assertEqual('new-id', change.to_dict()['id'])

    def test_set_attr_document(self):
        change = Change(id='id', sequence_id='', document={})
        self.assertEqual({}, change.document)
        document = {'foo': 'bar'}
        change.set_document(document)
        self.assertEqual(document, change.document)
        self.assertEqual(document, change.to_dict()['doc'])

    def test_set_attr_seq(self):
        change = Change(id='id', sequence_id='seq')
        self.assertEqual('seq', change.sequence_id)
        change.sequence_id = 'seq-2'
        self.assertEqual('seq-2', change.sequence_id)
        self.assertEqual('seq-2', change.to_dict()['seq'])

    def test_set_attr_deleted(self):
        change = Change(id='id', sequence_id='', deleted=True)
        self.assertTrue(change.deleted)
        change.deleted = False
        self.assertFalse(change.deleted)
        self.assertFalse(change.to_dict()['deleted'])


class TestChangeDocument(SimpleTestCase):

    def setUp(self):
        # bootstrap a dao with a doc in it
        self.dao = MockDocumentStore()
        self.doc_id = uuid.uuid4().hex
        self.doc = {'id': self.doc_id, 'random_property': uuid.uuid4().hex}
        self.dao.save_document(self.doc_id, self.doc)

    def test_get_set_document(self):
        change = Change(id='id', sequence_id='')
        self.assertEqual(None, change.get_document())
        doc = {'test': '123'}
        change.set_document(doc)
        self.assertEqual(doc, change.get_document())

    def test_get_document_from_doc_store(self):
        change = Change(id=self.doc_id, sequence_id='', document_store=self.dao)
        self.assertEqual(self.doc, change.get_document())

    def test_initial_document_overrides_doc_store(self):
        change = Change(id=self.doc_id, sequence_id='', document={'not': 'expected'}, document_store=self.dao)
        self.assertNotEqual(self.doc, change.get_document())

    def test_set_document_overrides_doc_store(self):
        change = Change(id=self.doc_id, sequence_id='', document_store=self.dao)
        self.assertEqual(self.doc, change.get_document())
        change.set_document({'something': 'else'})
        self.assertNotEqual(self.doc, change.get_document())

    def test_get_document_not_found(self):
        change = Change(id=uuid.uuid4().hex, sequence_id='', document_store=self.dao)
        self.assertEqual(None, change.get_document())


class TestMockChangeFeed(SimpleTestCase):

    def test_len(self):
        feed = MockChangeFeed(['test'] * 5)
        self.assertEqual(5, len(list(feed.iter_changes(0))))
        self.assertEqual(3, len(list(feed.iter_changes(2))))
        self.assertEqual(0, len(list(feed.iter_changes(5))))
        self.assertEqual(0, len(list(feed.iter_changes(10))))

    def test_results(self):
        feed = MockChangeFeed(list(range(5)))
        changes = feed.iter_changes(0)
        for seq, change in enumerate(changes):
            self.assertEqual(seq, change)


class TestRandomChangeFeed(SimpleTestCase):

    def test_len(self):
        feed = RandomChangeFeed(5)
        self.assertEqual(5, len(list(feed.iter_changes(0))))
        self.assertEqual(3, len(list(feed.iter_changes(2))))
        self.assertEqual(0, len(list(feed.iter_changes(5))))
        self.assertEqual(0, len(list(feed.iter_changes(10))))

    def test_results(self):
        feed = RandomChangeFeed(5)
        changes = feed.iter_changes(0)
        ids = set()
        for seq, change in enumerate(changes):
            self.assertTrue(isinstance(change, Change))
            self.assertEqual(seq, change.sequence_id)
            self.assertEqual(None, change.document)
            self.assertEqual(False, change.deleted)
            self.assertTrue(change.id not in ids)
            ids.add(change.id)

    def test_override_fn(self):
        val = object()
        feed = RandomChangeFeed(5, change_generator=lambda seq: val)
        changes = feed.iter_changes(0)
        for change in changes:
            self.assertEqual(val, change)
