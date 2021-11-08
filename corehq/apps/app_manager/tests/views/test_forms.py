from django.test import SimpleTestCase
from ...views.forms import _is_valid_xform


class TestXFormValidation(SimpleTestCase):
    def test_normal_form_is_valid(self):
        form = '''
        <html>
            <head>
                <title>Survery</title>
            </head>
        </html>
        '''.strip()
        self.assertTrue(_is_valid_xform(form))

    def test_form_with_entity_only_in_dtd_is_valid(self):
        form = '''
        <!DOCTYPE foo [<!ENTITY example SYSTEM 'file://etc/hosts'>]>
        <html>
            <head>
                <title>Survery</title>
            </head>
        </html>
        '''.strip()
        self.assertTrue(_is_valid_xform(form))

    def test_form_referencing_entity_is_invalid(self):
        form = '''
        <!DOCTYPE foo [<!ENTITY example SYSTEM 'file://etc/hosts'>]>
        <html>
            <head>
                <title>Survery: &example;</title>
            </head>
        </html>
        '''.strip()
        self.assertFalse(_is_valid_xform(form))
