from __future__ import absolute_import
from __future__ import unicode_literals

import uuid

from couchdbkit import ResourceNotFound
from django.test import SimpleTestCase, TestCase
from mock import patch

from corehq.apps.app_manager.models import Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


class ReleaseFormsSetupMixin(object):
    def set_up_app(self):
        self.factory = AppFactory(build_version='2.30.0')
        training_module = self.factory.app.add_module(Module.new_training_module('training module', None))
        self.releases_form = self.factory.app.new_form(training_module.id, "Untitled Form", None)
        self.releases_form.is_release_notes_form=True
        self.releases_form.xmlns = "http://openrosa.org/formdesigner/{}".format(uuid.uuid4().hex)
        basic_module, self.basic_form = self.factory.new_basic_module("basic_module", "doctor", with_form=True)
        self.basic_form.xmlns = "http://openrosa.org/formdesigner/{}".format(uuid.uuid4().hex)


class ReleaseFormsEnabledTest(SimpleTestCase, ReleaseFormsSetupMixin, TestXmlMixin):

    def setUp(self):
        self.set_up_app()
        self.releases_form.enable_release_notes = True
        super(ReleaseFormsEnabledTest, self).setUp()

    def test_resource(self):
        # release form should be as xform-update-info
        suite = self.factory.app.create_suite()
        xpath = "./xform-update-info"
        expected = """
            <partial>
              <xform-update-info>
                <resource id="{id}" descriptor="Form: (Module training module) - Untitled Form">
                  <location authority="local">./modules-0/forms-0.xml</location>
                  <location authority="remote">./modules-0/forms-0.xml</location>
                </resource>
              </xform-update-info>
            </partial>
        """.format(id=self.releases_form.unique_id)
        self.assertXmlPartialEqual(expected, suite, xpath)
        # normal form should be still under xform
        xpath = "./xform"
        expected = """
            <partial>
              <xform>
                <resource id="basic_module_form_0" descriptor="Form: (Module basic_module module) - basic_module form 0">
                  <location authority="local">./modules-1/forms-0.xml</location>
                  <location authority="remote">./modules-1/forms-0.xml</location>
                </resource>
              </xform>
            </partial>
        """
        # not included in resource
        self.assertXmlPartialEqual(expected, suite, xpath)

    def test_entry(self):
        suite = self.factory.app.create_suite()
        expected = """
            <partial>
              <entry>
                <form>{release_xmlns}</form>
                <command id="m0-f0">
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                </command>
              </entry>
              <entry>
                <form>{basic_xmlns}</form>
                <command id="m1-f0">
                  <text>
                    <locale id="forms.m1f0"/>
                  </text>
                </command>
              </entry>
            </partial>
        """.format(
            release_xmlns=self.releases_form.xmlns,
            basic_xmlns=self.basic_form.xmlns)
        # check entry exists
        self.assertXmlPartialEqual(expected, suite, "./entry")

    def test_command(self):
        # check command in suite/menu exists
        suite = self.factory.app.create_suite()
        expected = """
        <partial>
            <menu id="m0" root="training-root" >
              <text>
                <locale id="modules.m0"/>
              </text>
              <command id="m0-f0"/>
            </menu>
            <menu id="m1">
              <text>
                <locale id="modules.m1"/>
              </text>
              <command id="m1-f0"/>
            </menu>
            <menu id="training-root">
              <text>
                <locale id="training.root.title"/>
              </text>
            </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./menu")


class ReleaseFormsDisabledTest(SimpleTestCase, ReleaseFormsSetupMixin, TestXmlMixin):

    def setUp(self):
        self.set_up_app()
        self.releases_form.enable_release_notes = False
        super(ReleaseFormsDisabledTest, self).setUp()

    def test_resource(self):
        # release form should be as xform-update-info
        suite = self.factory.app.create_suite()
        xpath = "./xform-update-info"
        self.assertXmlDoesNotHaveXpath(suite, xpath)
        expected = """
            <partial>
              <xform>
                <resource id="basic_module_form_0" descriptor="Form: (Module basic_module module) - basic_module form 0">
                  <location authority="local">./modules-1/forms-0.xml</location>
                  <location authority="remote">./modules-1/forms-0.xml</location>
                </resource>
              </xform>
            </partial>
        """
        self.assertXmlPartialEqual(expected, suite, './xform')

    def test_entry(self):
        suite = self.factory.app.create_suite()
        expected = """
            <partial>
              <entry>
                <form>{basic_xmlns}</form>
                <command id="m1-f0">
                  <text>
                    <locale id="forms.m1f0"/>
                  </text>
                </command>
              </entry>
            </partial>
        """.format(
            basic_xmlns=self.basic_form.xmlns)
        # check entry exists
        self.assertXmlPartialEqual(expected, suite, "./entry")

    def test_command(self):
        # check command in suite/menu exists
        suite = self.factory.app.create_suite()
        expected = """
        <partial>
            <menu id="m1">
              <text>
                <locale id="modules.m1"/>
              </text>
              <command id="m1-f0"/>
            </menu>
            <menu id="training-root">
              <text>
                <locale id="training.root.title"/>
              </text>
            </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./menu")


class ReleaseNotesResourceFileTest(TestCase, ReleaseFormsSetupMixin, TestXmlMixin):
    file_path = ('data',)

    def setUp(self):
        self.set_up_app()
        self.releases_form.source = self.get_xml('very_simple_form').decode('utf-8')
        self.basic_form.source = self.get_xml('very_simple_form').decode('utf-8')
        self.factory.app.save()

        super(ReleaseNotesResourceFileTest, self).setUp()

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @patch('corehq.apps.app_manager.models.FormBase.is_a_disabled_release_form', return_value=False)
    def test_enabled(self, *args):
        # check form in resource files
        self.factory.app.create_build_files()
        copy = self.factory.app.make_build()
        copy.save()
        self.assertTrue(copy.lazy_fetch_attachment('files/modules-0/forms-0.xml'))

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @patch('corehq.apps.app_manager.models.FormBase.is_a_disabled_release_form', return_value=True)
    def test_disabled(self, *args):
        self.factory.app.create_build_files()
        copy = self.factory.app.make_build()
        copy.save()
        with self.assertRaises(ResourceNotFound):
            self.assertTrue(copy.lazy_fetch_attachment('files/modules-0/forms-0.xml'))
