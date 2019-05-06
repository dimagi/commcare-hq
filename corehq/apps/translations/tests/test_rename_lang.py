# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application, Module


class RenameLangTest(SimpleTestCase):

    def test_rename_lang_empty_form(self):
        app = Application.new_app('domain', "Untitled Application")
        module = app.add_module(Module.new_module('module', None))
        form1 = app.new_form(module.id, "Untitled Form", None)
        form1.source = '<source>'

        # form with no source
        form2 = app.new_form(module.id, "Empty form", None)

        app.rename_lang('en', 'fra')

        self.assertNotIn('en', module.name)
        self.assertIn('fra', module.name)

        self.assertNotIn('en', form1.name)
        self.assertIn('fra', form1.name)

        self.assertNotIn('en', form2.name)
        self.assertIn('fra', form2.name)
