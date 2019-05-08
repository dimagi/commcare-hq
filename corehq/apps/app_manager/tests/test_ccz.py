# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.hqmedia.tasks import find_missing_locale_ids_in_ccz


class CCZTest(TestCase):
    def setUp(self):
        self.factory = AppFactory(build_version='2.40.0', domain='domain')
        self.module, self.form = self.factory.new_basic_module('basic', 'patient')

        builder = XFormBuilder(self.form.name)
        builder.new_question(name='name', label='Name')
        self.form.source = builder.tostring(pretty_print=True).decode('utf-8')

    def test_missing_locale_ids(self):
        files = self.factory.app.create_all_files()
        errors = find_missing_locale_ids_in_ccz(files)
        self.assertEqual(len(errors), 0)

        default_app_strings = files['default/app_strings.txt'].splitlines()
        files['default/app_strings.txt'] = "\n".join([line for line in default_app_strings
                                                      if not line.startswith("forms.m0f0")])
        errors = find_missing_locale_ids_in_ccz(files)
        self.assertEqual(len(errors), 1)
        self.assertIn('forms.m0f0', errors[0])
