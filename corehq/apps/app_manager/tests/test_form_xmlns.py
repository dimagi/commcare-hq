# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.apps.app_manager.models import AdvancedModule, Application, Module
from corehq.apps.app_manager.util import save_xform

from corehq.apps.app_manager.tests.util import TestXmlMixin

XMLNS_PREFIX = 'http://openrosa.org/formdesigner/'
GENERIC_XMLNS = "http://www.w3.org/2002/xforms"
DEFAULT_XMLNS = XMLNS_PREFIX + 'A22A5D53-037A-48DE-979B-BAA54734194E'


class FormXmlnsTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def setUp(self):
        self.app = Application.new_app('domain', "Application")
        self.module = self.app.add_module(Module.new_module('module', None))
        self.form = self.app.new_form(self.module.id, "Form", None)
        self.assertNotEqual(self.form.xmlns, DEFAULT_XMLNS)

    def get_source(self, xmlns=DEFAULT_XMLNS):
        default_xmlns = DEFAULT_XMLNS
        xmlns_tag = ' xmlns="%s"' % default_xmlns
        source = self.get_xml('original_form')
        assert xmlns_tag in source, source
        if xmlns is None:
            source = source.replace(xmlns_tag, '')
        else:
            if xmlns != default_xmlns:
                source = source.replace(default_xmlns, xmlns)
            assert xmlns in source, source
        return source

    def test_save_xform_changes_empty_xmlns(self):
        source = self.get_source(xmlns=None)
        self.assertNotIn(self.form.xmlns, source)
        save_xform(self.app, self.form, source)
        self.assertIn(self.form.xmlns, self.form.source)
        self.assertNotEqual(self.form.xmlns, GENERIC_XMLNS)

    def test_save_xform_changes_generic_xmlns(self):
        source = self.get_source(xmlns=GENERIC_XMLNS)
        self.assertNotIn(self.form.xmlns, source)
        save_xform(self.app, self.form, source)
        self.assertIn(self.form.xmlns, self.form.source)
        self.assertNotEqual(self.form.xmlns, GENERIC_XMLNS)

    def test_save_xform_does_not_change_xmlns_if_already_unique(self):
        source = self.get_source()
        form = self.form
        save_xform(self.app, form, source)
        self.assertEqual(form.source, source)
        self.assertEqual(form.xmlns, DEFAULT_XMLNS)
        # clear cach because form.xmlns changed in save_xform
        Application.get_xmlns_map.get_cache(self.app).clear()
        self.assertEqual(self.app.get_xmlns_map().get(form.xmlns), [form])

    def test_save_xform_with_conflicting_xmlns_sets_new_xmlns(self):
        source = self.get_source()
        save_xform(self.app, self.form, source)
        self.assertEqual(self.form.source, source)

        # clear cach because form.xmlns changed in save_xform
        Application.get_xmlns_map.get_cache(self.app).clear()
        form2 = self.app.new_form(self.module.id, "Form 2", None)
        form2_xmlns = form2.xmlns
        self.assertNotIn(form2_xmlns, source)
        save_xform(self.app, form2, source)
        self.assertIn(form2_xmlns, form2.source)
        self.assertNotIn(DEFAULT_XMLNS, form2.source)

    def test_save_xform_with_shadow_form_does_not_change_xmlns(self):
        source = self.get_source()
        module = self.app.add_module(AdvancedModule.new_module('a module', None))
        form = self.app.new_form(self.module.id, "a form", None)
        save_xform(self.app, form, source)
        Application.get_xmlns_map.get_cache(self.app).clear()

        shadow = module.new_shadow_form("shadow form", "en")
        shadow.shadow_parent_form_id = form.unique_id
        self.assertEqual(shadow.shadow_parent_form, form)

        save_xform(self.app, form, source)
        self.assertEqual(form.source, source)
        self.assertEqual(form.xmlns, DEFAULT_XMLNS)

    def test_copy_form_changes_xmlns(self):
        old_form = self.form
        old_form.source = self.get_source()

        new_form = self.app._copy_form(self.module, old_form, self.module)

        self.assertEqual(new_form.xmlns, XMLNS_PREFIX + new_form.unique_id)
        self.assertIn(new_form.xmlns, new_form.source)
        self.assertNotEqual(new_form.xmlns, old_form.xmlns)
        self.assertNotIn(old_form.xmlns, new_form.source)
        self.assertNotIn(new_form.xmlns, old_form.source)
