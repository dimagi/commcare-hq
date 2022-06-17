from django.test import SimpleTestCase

from ..models import ESCase


class ESCaseTests(SimpleTestCase):
    def test_handles_no_indices(self):
        case = ESCase({'indices': []})
        self.assertEqual(case.indices, [])

    def test_handles_index_with_doc_type(self):
        case = ESCase(
            {
                'indices': [{
                    'doc_type': 'CommCareCaseIndex',
                    'referenced_id': 'some_id'
                }]
            })
        index = case.indices[0]
        self.assertEqual(index.referenced_id, 'some_id')
