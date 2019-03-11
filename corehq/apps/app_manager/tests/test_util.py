from __future__ import absolute_import
from __future__ import unicode_literals

from django.http import Http404
from django.test.testcases import TestCase

from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    Module,
)
from corehq.apps.app_manager.util import LatestAppInfo
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
            app_config = self.app.global_app_config
            app_config.apk_prompt = config
            app_config.save()
            latest_info = LatestAppInfo(self.app.master_id, self.domain)
            self.assertEquals(
                latest_info.get_latest_apk_version(),
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
            latest_info = LatestAppInfo(self.app.master_id, self.domain)
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
            app_config = self.app.global_app_config
            app_config.app_prompt = config
            app_config.save()
            latest_info = LatestAppInfo(self.app.master_id, self.domain)
            self.assertEquals(
                latest_info.get_latest_app_version(),
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
            latest_info = LatestAppInfo(self.app.master_id, self.domain)
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
