# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestXmlMixin


class CaseListLookupTest(SimpleTestCase, TestXmlMixin):

    def test_case_list_lookup_wo_image(self):
        callout_action = "callout.commcarehq.org.dummycallout.LAUNCH"

        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
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

        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
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

    def test_case_list_lookup_w_name(self):
        action = "callout.commcarehq.org.dummycallout.LAUNCH"
        image = "jr://file/commcare/image/callout"
        name = u"ιтѕ α тяαρ ʕ •ᴥ•ʔ"

        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.lookup_enabled = True
        module.case_details.short.lookup_action = action
        module.case_details.short.lookup_image = image
        module.case_details.short.lookup_name = name

        expected = u"""
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
        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
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
        app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
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
