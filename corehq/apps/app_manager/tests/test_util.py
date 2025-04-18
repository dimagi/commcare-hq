from django.http import Http404
from django.test.testcases import TestCase, SimpleTestCase

from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    BuildProfile,
    GlobalAppConfig,
    LatestEnabledBuildProfiles,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    get_simple_form,
    patch_validate_xform,
    SuiteMixin,
)
from corehq.apps.app_manager.util import split_path, does_app_have_mobile_ucr_v1_refs
from corehq.apps.app_manager.views.utils import get_default_followup_form_xml
from corehq.apps.domain.models import Domain


class TestGetDefaultFollowupForm(TestCase):
    def test_default_followup_form(self):
        app = Application.new_app('domain', "Untitled Application")

        parent_module = app.add_module(AdvancedModule.new_module('parent', None))
        parent_module.case_type = 'parent'
        parent_module.unique_id = 'id_parent_module'

        context = {
            'lang': None,
            'default_label': "Default label message"
        }
        attachment = get_default_followup_form_xml(context=context)
        followup = app.new_form(0, "Followup Form", None, attachment=attachment)

        self.assertEqual(followup.name['en'], "Followup Form")
        self.assertEqual(app.modules[0].forms[0].name['en'], "Followup Form")

        first_question = app.modules[0].forms[0].get_questions([], include_triggers=True, include_groups=True)[0]
        self.assertEqual(first_question['label'], " Default label message ")


class TestGlobalAppConfig(TestCase):
    domain = 'test-latest-app'

    @classmethod
    @patch_validate_xform()
    def setUpClass(cls):
        super(TestGlobalAppConfig, cls).setUpClass()
        cls.project = Domain.get_or_create_with_name(cls.domain)

        cls.build_profile_id = 'english'
        factory = AppFactory(cls.domain, 'foo')
        m0, f0 = factory.new_basic_module("bar", "bar")
        f0.source = get_simple_form(xmlns=f0.unique_id)
        app = factory.app
        app.build_profiles = {
            cls.build_profile_id: BuildProfile(langs=['en'], name='English only'),
        }
        app.langs = ["en"]
        app.version = 1
        app.save()  # app is now v2

        cls.v2_build = app.make_build()
        cls.v2_build.is_released = True
        cls.v2_build.save()  # v2 is starred

        app.save()  # app is now v3
        cls.v3_build = app.make_build()
        cls.v3_build.is_released = True
        cls.v3_build.save()  # v3 is starred

        app.save()  # app is v4

        # Add a build-profile-specific release at v2
        cls.latest_profile = LatestEnabledBuildProfiles(
            domain=cls.domain,
            app_id=app.get_id,
            build_profile_id=cls.build_profile_id,
            version=cls.v2_build.version,
            build_id=cls.v2_build.get_id,
            active=True,
        )
        cls.latest_profile.save()

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
            ('off', '', {}),
            ('on', '', {'value': self.v3_build.version, 'force': False}),
            ('forced', '', {'value': self.v3_build.version, 'force': True}),
            ('off', self.build_profile_id, {}),
            ('on', self.build_profile_id, {'value': self.v2_build.version, 'force': False}),
            ('forced', self.build_profile_id, {'value': self.v2_build.version, 'force': True}),
        ]
        for config, build_profile_id, response in test_cases:
            app_config = self.app.global_app_config
            app_config.app_prompt = config
            app_config.save()
            config = GlobalAppConfig.by_app_id(self.domain, self.app.origin_id)
            self.assertEqual(
                config.get_latest_app_version(build_profile_id),
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
                config.get_latest_app_version(build_profile_id=''),
                response
            )

    def test_load_from_build(self):
        config = self._fresh_config(self.v3_build.id)
        with self.assertRaises(AssertionError):
            config.get_latest_app_version(build_profile_id='')

    def test_missing_app(self):
        config = self._fresh_config('missing_id')
        with self.assertRaises(Http404):
            config.get_latest_app_version(build_profile_id='')

    def test_latest_profile_serialize(self):
        self.assertEqual(
            self.latest_profile.to_json({self.app.get_id: self.app.name}),
            {
                'id': self.latest_profile.id,
                'app_id': self.app.get_id,
                'active': True,
                'version': self.v2_build.version,
                'build_profile_id': self.build_profile_id,
                'app_name': 'foo',
                'profile_name': 'English only'
            }
        )

    def _fresh_config(self, app_id):
        config = GlobalAppConfig.by_app_id(self.domain, app_id)
        config.app_prompt = 'on'
        return config


class TestSplitPath(SimpleTestCase):

    def test_path_filename(self):
        path, name = split_path('foo/bar/baz.txt')
        self.assertEqual(path, 'foo/bar')
        self.assertEqual(name, 'baz.txt')

    def test_no_slash(self):
        path, name = split_path('foo')
        self.assertEqual(path, '')
        self.assertEqual(name, 'foo')

    def test_empty_string(self):
        path, name = split_path('')
        self.assertEqual(path, '')
        self.assertEqual(name, '')


class TestDoesAppHaveMobileUCRV1Refs(TestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def _create_app_with_form(self, xml_source_name):
        app = Application.new_app('domain', "Untitled Application")
        app.add_module(AdvancedModule.new_module('module', None))
        app.new_form(
            module_id=0,
            name="My Form",
            lang=None,
            attachment=self.get_xml(xml_source_name).decode('utf-8')
        )
        return app

    def test_does_app_have_mobile_ucr_v1_refs(self):
        app_with_refs = self._create_app_with_form('reports_module_data_entry_mobile_ucr_v1')
        self.assertTrue(does_app_have_mobile_ucr_v1_refs(app_with_refs))
        app_without_refs = self._create_app_with_form('normal-suite')
        self.assertFalse(does_app_have_mobile_ucr_v1_refs(app_without_refs))
