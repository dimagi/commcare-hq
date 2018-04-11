# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


class CaseListLookupTest(SimpleTestCase, TestXmlMixin):

    def test_case_list_lookup_wo_image(self):
        callout_action = "callout.commcarehq.org.dummycallout.LAUNCH"

        app = Application.new_app('domain', 'Untitled Application')
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = callout_action

        expected = """
            <partial>
                <lookup action="{}"/>
            </partial>
        """.format(callout_action)

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_w_image(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        image = "jr://file/commcare/image/callout"

        app = Application.new_app('domain', 'Untitled Application')
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = action
        module.case_details.short.lookup_image = image

        expected = """
            <partial>
                <lookup action="{}" image="{}"/>
            </partial>
        """.format(action, image)

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_autolaunch(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        app = Application.new_app('domain', 'Untitled Application')
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_autolaunch = True
        module.case_details.short.lookup_action = action

        expected = """
            <partial>
                <lookup action="{action}" auto_launch="true"/>
            </partial>
        """.format(action=action)

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_w_name(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        image = "jr://file/commcare/image/callout"
        name = "ιтѕ α тяαρ ʕ •ᴥ•ʔ"

        app = Application.new_app('domain', 'Untitled Application')
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = action
        module.case_details.short.lookup_image = image
        module.case_details.short.lookup_name = name

        expected = """
            <partial>
                <lookup name="{}" action="{}" image="{}"/>
            </partial>
        """.format(name, action, image)

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_w_extras_and_responses(self):
        app = Application.new_app('domain', 'Untitled Application')
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = "callout.commcarehq.org.dummycallout.LAUNCH"
        module.case_details.short.lookup_extras = [
            {'key': 'action_0', 'value': 'com.biometrac.core.SCAN'},
            {'key': "action_1", 'value': "com.biometrac.core.IDENTIFY"},
        ]
        module.case_details.short.lookup_responses = [
            {"key": "match_id_0"},
            {"key": "match_id_1"},
        ]

        expected = """
        <partial>
            <lookup action="callout.commcarehq.org.dummycallout.LAUNCH">
                <extra key="action_0" value="com.biometrac.core.SCAN"/>
                <extra key="action_1" value="com.biometrac.core.IDENTIFY"/>
                <response key="match_id_0"/>
                <response key="match_id_1"/>
            </lookup>
        </partial>
        """

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_disabled(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        app = Application.new_app('domain', 'Untitled Application')
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = False
        module.case_details.short.lookup_action = action
        module.case_details.short.lookup_responses = ["match_id_0", "left_index"]

        expected = "<partial></partial>"

        self.assertXmlPartialEqual(
            expected,
            app.create_suite(),
            "./detail/lookup"
        )

    def test_case_list_lookup_display_results(self):
        factory = AppFactory(build_version='2.11')
        module, form = factory.new_basic_module('follow_up', 'case')
        case_list = module.case_details.short
        case_list.lookup_enabled = True
        case_list.lookup_action = "callout.commcarehq.org.dummycallout.LAUNCH"
        case_list.lookup_name = 'Scan fingerprint'
        case_list.lookup_extras = [
            {'key': 'deviceId', 'value': '123'},
            {'key': 'apiKey', 'value': '0000'},
            {'key': 'packageName', 'value': 'foo'},
        ]
        case_list.lookup_responses = [
            {'key': 'fake'}
        ]
        case_list.lookup_display_results = True
        case_list.lookup_field_header['en'] = 'Accuracy'
        case_list.lookup_field_template = '@case_id'
        expected = """
          <partial>
            <lookup name="Scan fingerprint"
                    action="callout.commcarehq.org.dummycallout.LAUNCH">
              <extra key="deviceId" value="123"/>
              <extra key="apiKey" value="0000"/>
              <extra key="packageName" value="foo"/>
              <response key="fake"/>
              <field>
                <header>
                  <text>
                    <locale id="case_lists.m0.callout.header"/>
                  </text>
                </header>
                <template>
                  <text>
                    <xpath function="@case_id"/>
                  </text>
                </template>
              </field>
            </lookup>
          </partial>
        """
        self.assertXmlPartialEqual(
            expected,
            factory.app.create_suite(),
            "./detail[@id='m0_case_short']/lookup"
        )
