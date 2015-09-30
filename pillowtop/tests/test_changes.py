from django.test import SimpleTestCase
from pillowtop.feed.couch import change_from_couch_row


class TestCouchChange(SimpleTestCase):

    def test_convert_to_and_from_couch_row(self):
        couch_row = {
            'id': 'an-id',
            'doc': {'a': 'document'},
            'seq': '21',
            'deleted': False
        }
        change = change_from_couch_row(couch_row)
        self.assertEqual('an-id', change.id)
        self.assertEqual(couch_row['doc'], change.document)
        self.assertEqual('21', change.sequence_id)
        self.assertEqual(False, change.deleted)
        for key in couch_row:
            self.assertEqual(couch_row[key], change[key])
