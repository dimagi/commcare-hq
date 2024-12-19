from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.cases import case_adapter

from ..es import CaseESView


@es_test(requires=[case_adapter])
class TestESView(SimpleTestCase):

    def test_get_document(self):
        doc_id = "1"
        doc_ny = {
            "_id": doc_id,
            "domain": "some-domain",
            "doc_type": CaseESView.doc_type,
            "location_id": "NYC",
            "backend_id": 'sql'
        }
        case_adapter.index(doc_ny, refresh=True)

        case_info = case_adapter.get(doc_id)
        case_info.pop('inserted_at')
        case_info.pop('owner_type')
        case_info.pop('doc_id')
        self.assertEqual(doc_ny, case_info)
        view = CaseESView(doc_ny["domain"])
        # test that the view fetches the doc by its ID as we'd expect
        self.assertEqual(case_adapter.get(doc_id), dict(view.get_document(doc_id)._data))
