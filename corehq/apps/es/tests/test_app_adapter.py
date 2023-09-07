from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test


@es_test(requires=[app_adapter], setup_class=True)
class TestFromPythonInApplication(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'from-python-application-tests'
        cls.app = cls._create_app(name='from-multi-test-app')
        cls.addClassCleanup(cls.app.delete_app)

    @classmethod
    def _create_app(self, name):
        factory = AppFactory(domain=self.domain, name=name, build_version='2.11.0')
        module1, form1 = factory.new_basic_module('open_case', 'house')
        factory.form_opens_case(form1)
        app = factory.app
        app.save()
        return app

    def test_from_python_works_with_application_objects(self):
        app_adapter.from_python(self.app)

    def test_from_python_works_with_application_dicts(self):
        app_adapter.from_python(self.app.to_json())

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, app_adapter.from_python, set)

    def test_index_can_handle_app_dicts(self):
        app_dict = self.app.to_json()
        app_adapter.index(app_dict, refresh=True)
        self.addCleanup(app_adapter.delete, self.app._id)

        app = app_adapter.to_json(self.app)
        app.pop('@indexed_on')
        es_app = app_adapter.search({})['hits']['hits'][0]['_source']
        es_app.pop('@indexed_on')
        self.assertEqual(es_app, app)

    def test_index_can_handle_app_objects(self):
        app_adapter.index(self.app, refresh=True)
        self.addCleanup(app_adapter.delete, self.app._id)

        app = app_adapter.to_json(self.app)
        app.pop('@indexed_on')
        es_app = app_adapter.search({})['hits']['hits'][0]['_source']
        es_app.pop('@indexed_on')

        self.assertEqual(es_app, app)
