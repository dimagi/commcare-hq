from django.test.testcases import TestCase

from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import (
    Application,
    ReportModule, ReportAppConfig, Module)
from corehq.apps.app_manager.remote_link_accessors import _convert_app_from_remote_linking_source
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.views.remote_linked_apps import _convert_app_for_remote_linking
from corehq.apps.app_manager.views.utils import overwrite_app


class TestLinkedApps(TestCase, TestXmlMixin):
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(TestLinkedApps, cls).setUpClass()
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

    def test_remote_app(self):
        module = self.master_app.add_module(Module.new_module('M1', None))
        module.new_form('f1', None, self.get_xml('very_simple_form'))

        master_source = _convert_app_for_remote_linking(self.master_app)
        master_app = _convert_app_from_remote_linking_source(master_source)

        overwrite_app(self.linked_app, master_app, {'id': 'mapped_id'})

        linked_app = Application.get(self.linked_app._id)
        self.assertEqual(self.master_app.get_attachments(), linked_app.get_attachments())
