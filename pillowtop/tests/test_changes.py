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
