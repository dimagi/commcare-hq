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


class TestGetFormData(SimpleTestCase):

    def test_advanced_form_get_action_type(self):
        app = Application.new_app('domain', "Untitled Application")

        parent_module = app.add_module(AdvancedModule.new_module('parent', None))
        parent_module.case_type = 'parent'
        parent_module.unique_id = 'id_parent_module'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m1-f0'
        form.actions.load_update_cases.append(LoadUpdateAction(case_type="clinic", case_tag='load_0'))

        modules, errors = util.get_form_data('domain', app)
        self.assertEqual(modules[0]['forms'][0]['action_type'], 'load (load_0)')


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
        cls.target_json = cls.linked_app.to_json()

    def test_missing_ucrs(self):
        with self.assertRaises(AppEditingError):
            overwrite_app(self.target_json, self.master_app, {})

    def test_report_mapping(self):
        report_map = {'id': 'mapped_id'}
        overwrite_app(self.target_json, self.master_app, report_map)
        linked_app = Application.get(self.linked_app._id)
        self.assertEqual(linked_app.modules[0].report_configs[0].report_id, 'mapped_id')


class TestLatestAppInfo(TestCase):
    domain = 'test-latest-app'

    @classmethod
    def setUpClass(cls):
        super(TestLatestAppInfo, cls).setUpClass()
        cls.project = Domain(name=cls.domain)
        cls.project.save()

        app = Application(
            domain=cls.domain,
            name='foo',
            langs=["en"],
            version=1,
            modules=[Module()]
        )  # app is v1

        app.save()  # app is v2
        cls.v2_build = app.make_build()
        cls.v2_build.is_released = True
        cls.v2_build.save()  # There is a starred build at v2

        app.save()  # app is v3
        app.make_build().save()  # There is a build at v3

        app.save()  # app is v4
        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestLatestAppInfo, cls).tearDownClass()

    def test_apk_prompt(self):
        from corehq.apps.builds.utils import get_default_build_spec
        latest_apk = get_default_build_spec().version
        test_cases = [
            ('off', {}),
            ('on', {'value': latest_apk, 'force': False}),
            ('forced', {'value': latest_apk, 'force': True}),
        ]
        for config, response in test_cases:
            self.app.latest_apk_prompt = config
            self.app.save()
            latest_info = LatestAppInfo(self.app.copy_of or self.app.id, self.domain)
            self.assertEquals(
                latest_info.get_latest_apk_version(),
                response
            )

    def test_app_prompt(self):
        test_cases = [
            ('off', {}),
            ('on', {'value': self.v2_build.version, 'force': False}),
            ('forced', {'value': self.v2_build.version, 'force': True}),
        ]
        for config, response in test_cases:
            self.app.latest_app_prompt = config
            self.app.save()
            latest_info = LatestAppInfo(self.app.copy_of or self.app.id, self.domain)
            self.assertEquals(
                latest_info.get_latest_app_version(),
                response
            )

    def test_args(self):
        with self.assertRaises(AssertionError):
            # should not be id of a copy
            LatestAppInfo(self.v2_build.id, self.domain).get_info()

        with self.assertRaises(Http404):
            LatestAppInfo('wrong-id', self.domain).get_info()
