from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.domains import domain_adapter
from corehq.pillows.domain import transform_domain_for_elasticsearch


@es_test(requires=[domain_adapter], setup_class=True)
class TestFromPythonInDomain(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'from-python-domain-tests'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def test_from_python_works_with_domain_objects(self):
        domain_adapter.from_python(self.domain_obj)

    def test_from_python_works_with_domain_dicts(self):
        domain_adapter.from_python(self.domain_obj.to_json())

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, domain_adapter.from_python, set)

    def test_from_python_is_same_as_transform_domain_for_es(self):
        # this test can be safely removed when transform_domain_for_elasticsearch is removed
        domain_id, domain = domain_adapter.from_python(self.domain_obj)
        domain['_id'] = domain_id
        self.assertEqual(transform_domain_for_elasticsearch(self.domain_obj.to_json()), domain)

    def test_index_can_handle_domain_dicts(self):
        domain_dict = self.domain_obj.to_json()
        domain_adapter.index(domain_dict, refresh=True)
        self.addCleanup(domain_adapter.delete, self.domain_obj._id)

        domain = domain_adapter.to_json(self.domain_obj)
        es_domain = domain_adapter.search({})['hits']['hits'][0]['_source']

        self.assertEqual(es_domain, domain)

    def test_index_can_handle_domain_objects(self):
        domain_adapter.index(self.domain_obj, refresh=True)
        self.addCleanup(domain_adapter.delete, self.domain_obj._id)

        domain = domain_adapter.to_json(self.domain_obj)
        es_domain = domain_adapter.search({})['hits']['hits'][0]['_source']

        self.assertEqual(es_domain, domain)
