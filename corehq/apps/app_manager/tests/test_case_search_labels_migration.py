from django.core.management import call_command
from django.test import TestCase

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import delete_all_apps


class TestCaseSearchLabelsMigration(TestCase):
    def setUp(self):
        self.domain = 'test-domain'
        self.factory = AppFactory(build_version='2.40.0', domain=self.domain)
        self.module, self.form = self.factory.new_basic_module('basic', 'patient')
        self.factory.app.save()

    @classmethod
    def tearDownClass(cls):
        delete_all_apps()
        super(TestCaseSearchLabelsMigration, cls).tearDownClass()

    def test_migration(self):
        # module without case search
        call_command('migrate_case_search_labels', domain=self.domain)

        self.assertEqual(self.module.search_config.search_label.label, {'en': 'Search All Cases'})
        self.assertEqual(self.module.search_config.search_again_label.label, {'en': 'Search Again'})

        # module with case search
        app, module = self._reload_app_and_module()
        module.search_config.command_label = {'en': 'Find my cases'}
        module.search_config.again_label = {'en': 'Find Again', 'fr': 'trouve encore'}
        app.save()

        call_command('migrate_case_search_labels', domain=self.domain)

        app, module = self._reload_app_and_module()
        self.assertEqual(module.search_config.search_label.label, {'en': 'Find my cases'})
        self.assertEqual(module.search_config.search_again_label.label,
                         {'en': 'Find Again', 'fr': 'trouve encore'})

    def _reload_app_and_module(self):
        app = get_app(self.domain, self.factory.app.get_id)
        return app, list(app.get_modules())[0]
