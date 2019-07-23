from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    AdvancedOpenCaseAction,
    LoadUpdateAction,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin, extract_xml_partial


class ShadowFormSuiteTest(SimpleTestCase, TestXmlMixin):

    def setUp(self):
        self.factory = AppFactory()
        self.advanced_module, self.form0 = self.factory.new_advanced_module('advanced_module', 'patient')
        self.form0.xmlns = 'http://openrosa.org/formdesigner/firstform'
        self.form0.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_type="patient",
                case_tag="open__0",
            )
        ]
        self.form0.actions.load_update_cases = [
            LoadUpdateAction(
                case_type="patient",
                case_tag="load_0",
                case_properties={
                    "name": "/data/name"
                },
                preload={
                    "/data/name": "name"
                },
                details_module=self.advanced_module.unique_id,
            )
        ]

        self.shadow_form = self.factory.new_shadow_form(self.advanced_module)
        self.shadow_form.shadow_parent_form_id = self.form0.unique_id
        # Shadow form load_update_case actions should contain all case tags from the parent
        self.shadow_form.extra_actions.load_update_cases = [
            LoadUpdateAction(
                case_type="patient",
                case_tag="load_0",
                details_module=self.advanced_module.unique_id,
            )
        ]

        self.basic_module = self.factory.new_basic_module("basic_module", "doctor", with_form=False)

    def test_resource_not_added(self):
        # Confirm that shadow forms do not add a <resource> node to the suite file
        suite = self.factory.app.create_suite()
        xpath = "./xform"
        # Note that the advanced_module only has one form, because the shadow form does not contribute an xform
        expected = """
            <partial>
              <xform>
                <resource id="advanced_module_form_0">
                  <location authority="local">./modules-0/forms-0.xml</location>
                  <location authority="remote">./modules-0/forms-0.xml</location>
                </resource>
              </xform>
            </partial>
        """
        self.assertXmlPartialEqual(expected, suite, xpath)

    def test_shadow_form_session_matches_parent(self):
        # Confirm that shadow form session matches shadow parent session.
        # This confirms that the parent load actions are properly transfered to the shadow form
        suite = self.factory.app.create_suite()
        shadow_source_session = extract_xml_partial(suite, "./entry/command[@id='m0-f0']/../session")
        shadow_form_session = extract_xml_partial(suite, "./entry/command[@id='m0-f1']/../session")
        self.assertXMLEqual(shadow_source_session.decode('utf-8'), shadow_form_session.decode('utf-8'))

    def test_shadow_form_entry_references_source_form(self):
        suite = self.factory.app.create_suite()
        xpath = "./entry/command[@id='m0-f1']/../form"
        expected = """
            <partial>
                <form>{}</form>
            </partial>
        """.format(self.form0.xmlns)
        self.assertXmlPartialEqual(expected, suite, xpath)

    def test_shadow_form_action_additions(self):
        # Confirm that shadow form action additions are reflected in the suite file
        original_actions = self.shadow_form.extra_actions.load_update_cases
        try:
            self.shadow_form.extra_actions.load_update_cases = [
                LoadUpdateAction(
                    case_type="patient",
                    case_tag="load_0",
                    details_module=self.advanced_module.unique_id,
                ),
                LoadUpdateAction(
                    case_tag="load_1",
                    case_type="doctor",
                    details_module=self.basic_module.unique_id
                )
            ]
            suite = self.factory.app.create_suite()
        finally:
            # reset the actions
            self.shadow_form.extra_actions.load_update_cases = original_actions

        # Confirm that the source session has not changed:
        expected_source_session = """
            <partial>
                <session>
                    <datum
                        detail-confirm="m0_case_long"
                        detail-select="m0_case_short"
                        id="case_id_load_0"
                        nodeset="instance('casedb')/casedb/case[@case_type='patient'][@status='open']"
                        value="./@case_id"
                    />
                    <datum function="uuid()" id="case_id_new_patient_0"/>
                </session>
            </partial>
        """
        self.assertXmlPartialEqual(expected_source_session, suite, "./entry/command[@id='m0-f0']/../session")

        # Confirm that the shadow session HAS changed:
        expected_shadow_session = """
            <partial>
                <session>
                    <datum
                        detail-confirm="m0_case_long"
                        detail-select="m0_case_short"
                        id="case_id_load_0"
                        nodeset="instance('casedb')/casedb/case[@case_type='patient'][@status='open']"
                        value="./@case_id"
                    />
                    <datum
                        detail-confirm="m1_case_long"
                        detail-select="m1_case_short"
                        id="case_id_load_1"
                        nodeset="instance('casedb')/casedb/case[@case_type='doctor'][@status='open']"
                        value="./@case_id"
                    />
                    <datum function="uuid()" id="case_id_new_patient_0"/>
                </session>
            </partial>
        """
        self.assertXmlPartialEqual(expected_shadow_session, suite, "./entry/command[@id='m0-f1']/../session")

    def test_shadow_form_action_modifications(self):
        # Confirm that shadow form action modifications are reflected in the suite file
        original_actions = self.shadow_form.extra_actions.load_update_cases
        try:
            self.shadow_form.extra_actions.load_update_cases = [
                LoadUpdateAction(
                    case_tag="load_0",
                    case_type="doctor",
                    details_module=self.basic_module.unique_id
                )
            ]
            suite = self.factory.app.create_suite()
        finally:
            # reset the actions
            self.shadow_form.extra_actions.load_update_cases = original_actions

        # Confirm that the source session has not changed:
        expected_source_session = """
            <partial>
                <session>
                    <datum
                        detail-confirm="m0_case_long"
                        detail-select="m0_case_short"
                        id="case_id_load_0"
                        nodeset="instance('casedb')/casedb/case[@case_type='patient'][@status='open']"
                        value="./@case_id"
                    />
                    <datum function="uuid()" id="case_id_new_patient_0"/>
                </session>
            </partial>
        """
        self.assertXmlPartialEqual(expected_source_session, suite, "./entry/command[@id='m0-f0']/../session")

        # Confirm that the shadow session HAS changed:
        expected_shadow_session = """
            <partial>
                <session>
                    <datum
                        detail-confirm="m1_case_long"
                        detail-select="m1_case_short"
                        id="case_id_load_0"
                        nodeset="instance('casedb')/casedb/case[@case_type='doctor'][@status='open']"
                        value="./@case_id"
                    />
                    <datum function="uuid()" id="case_id_new_patient_0"/>
                </session>
            </partial>
        """
        self.assertXmlPartialEqual(expected_shadow_session, suite, "./entry/command[@id='m0-f1']/../session")

    def test_shadow_form_action_reordering(self):
        # Confirm that the ordering of the actions in the shadow form is used, not the source ordering

        source_form_original_actions = self.form0.actions.load_update_cases
        shadow_form_original_actions = self.shadow_form.extra_actions.load_update_cases
        try:
            # Add an action to the source form
            self.form0.actions.load_update_cases = [
                LoadUpdateAction(
                    case_type="patient",
                    case_tag="load_0",
                    case_properties={
                        "name": "/data/name"
                    },
                    preload={
                        "/data/name": "name"
                    },
                    details_module=self.advanced_module.unique_id,
                ),
                LoadUpdateAction(
                    case_type="patient",
                    case_tag="load_1",
                    case_properties={
                        "name": "/data/name"
                    },
                    preload={
                        "/data/name": "name"
                    },
                    details_module=self.advanced_module.unique_id,
                )
            ]

            # specify a different order in the shadow form
            self.shadow_form.extra_actions.load_update_cases = [
                LoadUpdateAction(
                    case_tag="load_1",
                    case_type="patient",
                    details_module=self.advanced_module.unique_id,
                ),
                LoadUpdateAction(
                    case_tag="load_0",
                    case_type="patient",
                    details_module=self.advanced_module.unique_id,
                )
            ]
            suite = self.factory.app.create_suite()

        finally:
            # reset the actions
            self.form0.actions.load_update_cases = source_form_original_actions
            self.shadow_form.extra_actions.load_update_cases = shadow_form_original_actions

        # Confirm that the load_0 action comes first in the source form
        self.assertXmlHasXpath(
            suite, "./entry/command[@id='m0-f0']/../session/datum[@id='case_id_load_0' and position() = 1]"
        )
        self.assertXmlHasXpath(
            suite, "./entry/command[@id='m0-f0']/../session/datum[@id='case_id_load_1' and position() = 2]"
        )

        # Confirm that the load_0 action comes second in the shadow form
        self.assertXmlHasXpath(
            suite, "./entry/command[@id='m0-f1']/../session/datum[@id='case_id_load_1' and position() = 1]"
        )
        self.assertXmlHasXpath(
            suite, "./entry/command[@id='m0-f1']/../session/datum[@id='case_id_load_0' and position() = 2]"
        )
