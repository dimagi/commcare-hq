# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import CaseXPathValidationError
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from mock import patch


class FormFilterErrorTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.suite_xml_is_usercase_in_use_patch = patch(
            'corehq.apps.app_manager.suite_xml.sections.menus.is_usercase_in_use'
        )
        self.suite_xml_is_usercase_in_use_mock = self.suite_xml_is_usercase_in_use_patch.start()
        self.factory = AppFactory(build_version='2.9')

    def tearDown(self):
        self.suite_xml_is_usercase_in_use_patch.stop()

    def test_error_when_no_case(self):
        self.suite_xml_is_usercase_in_use_mock.return_value = True

        __, reg_form = self.factory.new_basic_module('reg_module', 'mother')
        self.factory.form_opens_case(reg_form)
        reg_form.form_filter = './due_date <= today()'

        with self.assertRaises(CaseXPathValidationError):
            self.factory.app.create_suite()

    def test_no_error_when_user_case(self):
        self.suite_xml_is_usercase_in_use_mock.return_value = True

        __, reg_form = self.factory.new_basic_module('reg_module', 'mother')
        self.factory.form_opens_case(reg_form)
        reg_form.form_filter = '#user/due_date <= today()'

        expected = """
        <partial>
            <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0" relevant="instance('casedb')/casedb/case[@case_type='commcare-user'][hq_user_id=instance('commcaresession')/session/context/userid]/due_date &lt;= today()"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, self.factory.app.create_suite(), './menu')

    def test_no_error_when_case(self):
        self.suite_xml_is_usercase_in_use_mock.return_value = False

        __, update_form = self.factory.new_basic_module('update_mother', 'mother')
        self.factory.form_requires_case(update_form)
        update_form.form_filter = '#case/due_date <= today()'

        expected = """
        <partial>
          <menu id="m0">
            <text>
              <locale id="modules.m0"/>
            </text>
            <command id="m0-f0" relevant="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]/due_date &lt;= today()"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, self.factory.app.create_suite(), './menu')
