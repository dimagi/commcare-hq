import json

from django.test import SimpleTestCase

from corehq.util.test_utils import generate_cases
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import PillowBase
from pillowtop.utils import prepare_bulk_payloads
from six.moves import range


class BulkTest(SimpleTestCase):

    def test_prepare_bulk_payloads_unicode(self):
        unicode_domain = 'हिंदी'
        bulk_changes = [
            {'id': 'doc1'},
            {'id': 'doc2', 'domain': unicode_domain},
        ]
        payloads = prepare_bulk_payloads(bulk_changes, max_size=10, chunk_size=1)
        self.assertEqual(2, len(payloads))
        self.assertEqual(unicode_domain, json.loads(payloads[1])['domain'])

    def test_deduplicate_changes(self):
        changes = [
            Change(1, 'a'),
            Change(2, 'a'),
            Change(3, 'a'),
            Change(2, 'b'),
            Change(4, 'a'),
            Change(1, 'b'),
        ]
        deduped = PillowBase._deduplicate_changes(changes)
        self.assertEqual(
            [(change.id, change.sequence_id) for change in deduped],
            [(3, 'a'), (2, 'b'), (4, 'a'), (1, 'b')]
        )


@generate_cases([
    (100, 1, 3),
    (100, 10, 1),
    (1, 1, 10),
    (1, 2, 5),
], BulkTest)
def test_prepare_bulk_payloads2(self, max_size, chunk_size, expected_payloads):
    bulk_changes = [{'id': 'doc%s' % i} for i in range(10)]
    payloads = prepare_bulk_payloads(bulk_changes, max_size=max_size, chunk_size=chunk_size)
    self.assertEqual(expected_payloads, len(payloads))
    self.assertTrue(all(payloads))

    # check that we can reform the original list of changes
    json_docs = b''.join(payloads).strip().split(b'\n')
    reformed_changes = [json.loads(doc) for doc in json_docs]
    self.assertEqual(bulk_changes, reformed_changes)
