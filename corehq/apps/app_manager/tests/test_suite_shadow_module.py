# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from corehq.apps.app_manager.tests.util import SuiteMixin, TestXmlMixin

class ShadowModuleSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def test_shadow_module(self):
        self._test_generic_suite('shadow_module')

    def test_shadow_module_forms_only(self):
        self._test_generic_suite('shadow_module_forms_only')

    def test_shadow_module_cases(self):
        self._test_generic_suite('shadow_module_cases')
