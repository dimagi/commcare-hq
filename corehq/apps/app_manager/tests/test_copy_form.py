from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application, AdvancedModule


class CopyFormTest(SimpleTestCase):
    def test_copy_form(self, *args):
        app = Application.new_app('domain', "Untitled Application")
        module = app.add_module(AdvancedModule.new_module('module', None))
        original_form = app.new_form(module.id, "Untitled Form", None)
        original_form.source = '<source>'

        app.copy_form(module, original_form, module, rename=True)

        form_count = 0
        for f in app.get_forms():
            form_count += 1
            if f.unique_id != original_form.unique_id:
                self.assertEqual(f.name['en'], 'Copy of {}'.format(original_form.name['en']))
        self.assertEqual(form_count, 2, 'Copy form has copied multiple times!')

    def test_copy_form_to_app(self, *args):
        src_app = Application.new_app('domain', "Source Application")
        src_module = src_app.add_module(AdvancedModule.new_module('Source Module', None))
        original_form = src_app.new_form(src_module.id, "Untitled Form", None)
        original_form.source = '<source>'
        dst_app = Application.new_app('domain', "Destination Application")
        dst_module = dst_app.add_module(AdvancedModule.new_module('Destination Module', None))

        src_app.copy_form(src_module, original_form, dst_module, rename=True)

        self.assertEqual(len(list(src_app.get_forms())), 1, 'Form copied to the wrong app')
        dst_app_forms = list(dst_app.get_forms())
        self.assertEqual(len(dst_app_forms), 1)
        self.assertEqual(dst_app_forms[0].name['en'], 'Copy of Untitled Form')
