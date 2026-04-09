from django.test import SimpleTestCase, TestCase

from django.http import Http404

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.models import Domain

from ..models import (
    FormAction,
    GlobalAppConfig,
    OpenCaseAction,
    UpdateCaseAction,
)


class FormActionTests(SimpleTestCase):

    def test_get_action_properties_for_name_update(self):
        action = OpenCaseAction({'name_update': {'question_path': '/data/name'}})
        properties = list(FormAction.get_action_properties(action))

        assert properties == [('name', '/data/name')]

    def test_get_action_properties_for_update(self):
        action = UpdateCaseAction({'update': {'one': {'question_path': 'q1'}}})
        properties = list(FormAction.get_action_properties(action))

        assert properties == [('one', 'q1')]


class TestGlobalAppConfig(TestCase):
    domain = 'test-latest-app'

    @classmethod
    @patch_validate_xform()
    def setUpClass(cls):
        super(TestGlobalAppConfig, cls).setUpClass()
        cls.project = Domain.get_or_create_with_name(cls.domain)

        factory = AppFactory(cls.domain, 'foo')
        m0, f0 = factory.new_basic_module("bar", "bar")
        f0.source = get_simple_form(xmlns=f0.unique_id)
        app = factory.app
        app.langs = ["en"]
        app.version = 1
        app.save()  # app is now v2

        cls.v2_build = app.make_build()
        cls.v2_build.is_released = True
        cls.v2_build.save()  # v2 is starred

        app.save()  # app is now v3

        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestGlobalAppConfig, cls).tearDownClass()

    def test_apk_prompt(self):
        from corehq.apps.builds.utils import get_default_build_spec
        latest_apk = get_default_build_spec().version
        test_cases = [
            ('off', {}),
            ('on', {'value': latest_apk, 'force': False}),
            ('forced', {'value': latest_apk, 'force': True}),
        ]
        for config, response in test_cases:
            app_config = self.app.global_app_config
            app_config.apk_prompt = config
            app_config.save()
            config = GlobalAppConfig.by_app_id(self.domain, self.app.origin_id)
            self.assertEqual(
                config.get_latest_apk_version(),
                response
            )

    def test_apk_prompt_preset(self):
        preset_apk = '2.20.0/latest'  # some random version
        test_cases = [
            ('off', {}),
            ('on', {'value': '2.20.0', 'force': False}),
            ('forced', {'value': '2.20.0', 'force': True}),
        ]
        app_config = self.app.global_app_config
        app_config.apk_version = preset_apk
        app_config.save()
        for config, response in test_cases:
            app_config = self.app.global_app_config
            app_config.apk_prompt = config
            app_config.save()
            config = GlobalAppConfig.by_app_id(self.domain, self.app.origin_id)
            self.assertEqual(
                config.get_latest_apk_version(),
                response
            )

    def test_app_prompt(self):
        app_config = self.app.global_app_config
        app_config.save()
        test_cases = [
            ('off', {}),
            ('on', {'value': self.v2_build.version, 'force': False}),
            ('forced', {'value': self.v2_build.version, 'force': True}),
        ]
        for config, response in test_cases:
            app_config = self.app.global_app_config
            app_config.app_prompt = config
            app_config.save()
            config = GlobalAppConfig.by_app_id(self.domain, self.app.origin_id)
            self.assertEqual(
                config.get_latest_app_version(),
                response
            )

    def test_app_prompt_preset(self):
        preset_app = 21  # some random version
        test_cases = [
            ('off', {}),
            ('on', {'value': preset_app, 'force': False}),
            ('forced', {'value': preset_app, 'force': True}),
        ]
        app_config = self.app.global_app_config
        app_config.app_version = preset_app
        app_config.save()
        for config, response in test_cases:
            app_config = self.app.global_app_config
            app_config.app_prompt = config
            app_config.save()
            config = GlobalAppConfig.by_app_id(self.domain, self.app.origin_id)
            self.assertEqual(
                config.get_latest_app_version(),
                response
            )

    def test_load_from_build(self):
        config = self._fresh_config(self.v2_build.id)
        with self.assertRaises(AssertionError):
            config.get_latest_app_version()

    def test_missing_app(self):
        config = self._fresh_config('missing_id')
        with self.assertRaises(Http404):
            config.get_latest_app_version()

    def _fresh_config(self, app_id):
        config = GlobalAppConfig.by_app_id(self.domain, app_id)
        config.app_prompt = 'on'
        return config
