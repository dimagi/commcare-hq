from django.test.testcases import SimpleTestCase, TestCase
from django.http import Http404

import corehq.apps.app_manager.util as util
from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    LoadUpdateAction,
    ReportModule, ReportAppConfig, Module)
from corehq.apps.app_manager.util import LatestAppInfo
from corehq.apps.app_manager.views.utils import overwrite_app
from corehq.apps.domain.models import Domain


class TestOverwriteApp(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestOverwriteApp, cls).setUpClass()
        cls.master_app = Application.new_app('domain', "Master Application")
        cls.linked_app = Application.new_app('domain-2', "Linked Application")
        module = cls.master_app.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [
            ReportAppConfig(report_id='id', header={'en': 'CommBugz'}),
        ]
        cls.linked_app.save()

    def test_missing_ucrs(self):
        with self.assertRaises(AppEditingError):
            overwrite_app(self.linked_app, self.master_app, {})

    def test_report_mapping(self):
        report_map = {'id': 'mapped_id'}
        overwrite_app(self.linked_app, self.master_app, report_map)
        linked_app = Application.get(self.linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')
