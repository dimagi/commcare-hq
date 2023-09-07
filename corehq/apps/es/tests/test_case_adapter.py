from django.test import TestCase

from corehq.apps.es.cases import case_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.tests.utils import create_case


@es_test(requires=[case_adapter], setup_class=True)
class TestFromPythonInCases(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'from-python-case-tests'
        cls.case = create_case(cls.domain, save=True)

    def test_from_python_works_with_case_objects(self):
        case_adapter.from_python(self.case)

    def test_from_python_works_with_case_dicts(self):
        case_adapter.from_python(self.case.to_json())

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, case_adapter.from_python, set)

    def test_index_can_handle_case_dicts(self):
        case_dict = self.case.to_json()
        case_adapter.index(case_dict, refresh=True)
        self.addCleanup(case_adapter.delete, self.case.case_id)

        case = case_adapter.to_json(self.case)
        case.pop('inserted_at')
        es_case = case_adapter.search({})['hits']['hits'][0]['_source']
        es_case.pop('inserted_at')
        self.assertEqual(es_case, case)

    def test_index_can_handle_case_objects(self):
        case_adapter.index(self.case, refresh=True)
        self.addCleanup(case_adapter.delete, self.case.case_id)

        case = case_adapter.to_json(self.case)
        case.pop('inserted_at')
        es_case = case_adapter.search({})['hits']['hits'][0]['_source']
        es_case.pop('inserted_at')
        self.assertEqual(es_case, case)
