# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.test import SimpleTestCase

from corehq.util.test_utils import generate_cases
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
    json_docs = ''.join(payloads).strip().split('\n')
    reformed_changes = [json.loads(doc) for doc in json_docs]
    self.assertEqual(bulk_changes, reformed_changes)
