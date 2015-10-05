from django.test import SimpleTestCase
from pillowtop.feed.couch import change_from_couch_row, force_to_change
from pillowtop.feed.interface import Change


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
            force_to_change(couch_row),
            force_to_change(force_to_change(couch_row)),  # tests passing an already converted object
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
        change.document = document
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
