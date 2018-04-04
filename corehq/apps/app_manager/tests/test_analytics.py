from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.app_manager.analytics import update_analytics_indexes, \
    get_exports_by_application
from corehq.apps.app_manager.models import Application, Module


class AnalyticsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(AnalyticsTest, cls).setUpClass()
        cls.domain = 'app-manager-analytics-test'
        cls.app = Application.new_app(cls.domain, "My App")
        cls.app.add_module(Module.new_module("My Module", 'en'))
        cls.app.get_module(0).new_form("My Form", 'en')
        cls.app.get_module(0).get_form(0).xmlns = 'myxmlns'
        cls.app.save()
        cls.app_id = cls.app.get_id
        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        super(AnalyticsTest, cls).tearDownClass()

    def test_get_exports_by_application(self):
        self.assertEqual(get_exports_by_application(self.domain), [{
            'value': {
                'app_deleted': False,
                'app': {
                    'langs': ['en'],
                    'name': 'My App',
                    'id': self.app_id
                },
                'xmlns': 'myxmlns',
                'form': {'name': {'en': 'My Form'}, 'id': 0},
                'module': {'name': {'en': 'My Module'}, 'id': 0}},
            'id': self.app_id,
            'key': ['app-manager-analytics-test', {}, 'myxmlns']
        }])
