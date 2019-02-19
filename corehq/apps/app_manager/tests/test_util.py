from __future__ import absolute_import
from __future__ import unicode_literals

from django.http import Http404
from django.test.testcases import TestCase

import corehq.apps.app_manager.util as util
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    LoadUpdateAction,
    Module,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.util import LatestAppInfo
from corehq.apps.app_manager.views.utils import get_default_followup_form_xml
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.domain.models import Domain


class TestGetFormData(TestCase):

    def test_form_data_with_case_properties(self):
        factory = AppFactory()
        app = factory.app
        module1, form1 = factory.new_basic_module('open_case', 'household')
        form1_builder = XFormBuilder(form1.name)

        # question 0
        form1_builder.new_question('name', 'Name')

        # question 1 (a group)
        form1_builder.new_group('demographics', 'Demographics')
        # question 2 (a question in a group)
        form1_builder.new_question('age', 'Age', group='demographics')

        # question 3 (a question that has a load property)
        form1_builder.new_question('polar_bears_seen', 'Number of polar bears seen')

        form1.source = form1_builder.tostring(pretty_print=True).decode('utf-8')
        factory.form_requires_case(form1, case_type='household', update={
            'name': '/data/name',
            'age': '/data/demographics/age',
        }, preload={
            '/data/polar_bears_seen': 'polar_bears_seen',
        })
        app.save()

        modules, errors = util.get_form_data(app.domain, app)

        q1_saves = modules[0]['forms'][0]['questions'][0]['save_properties'][0]
        self.assertEqual(q1_saves.case_type, 'household')
        self.assertEqual(q1_saves.property, 'name')

        group_saves = modules[0]['forms'][0]['questions'][2]['save_properties'][0]
        self.assertEqual(group_saves.case_type, 'household')
        self.assertEqual(group_saves.property, 'age')

        q3_loads = modules[0]['forms'][0]['questions'][3]['load_properties'][0]
        self.assertEqual(q3_loads.case_type, 'household')
        self.assertEqual(q3_loads.property, 'polar_bears_seen')

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

        modules, _ = util.get_form_data('domain', app)
        self.assertEqual(followup.name['en'], "Followup Form")
        self.assertEqual(modules[0]['forms'][0]['name']['en'], "Followup Form")
        self.assertEqual(modules[0]['forms'][0]['questions'][0]['label'], " Default label message ")


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
