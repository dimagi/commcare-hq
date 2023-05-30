from django.test import TestCase

from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.tests.utils import create_form_for_test


@es_test(requires=[form_adapter], setup_class=True)
class TestFromPythonInForms(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'from-python-forms-tests'
        cls.form = create_form_for_test(cls.domain, save=True)

    def test_from_python_works_with_form_objects(self):
        form_adapter.from_python(self.form)

    def test_from_python_works_with_form_dicts(self):
        form_adapter.from_python(self.form.to_json())

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, form_adapter.from_python, set)

    def test_index_can_handle_form_dicts(self):
        form_dict = self.form.to_json()
        form_adapter.index(form_dict, refresh=True)
        self.addCleanup(form_adapter.delete, self.form.form_id)

        form = form_adapter.to_json(self.form)
        form.pop('inserted_at')
        es_form = form_adapter.search({})['hits']['hits'][0]['_source']
        es_form.pop('inserted_at')
        self.assertEqual(es_form, form)

    def test_index_can_handle_form_objects(self):
        form_adapter.index(self.form, refresh=True)
        self.addCleanup(form_adapter.delete, self.form.form_id)

        form = form_adapter.to_json(self.form)
        form.pop('inserted_at')
        es_form = form_adapter.search({})['hits']['hits'][0]['_source']
        es_form.pop('inserted_at')
        self.assertEqual(es_form, form)
