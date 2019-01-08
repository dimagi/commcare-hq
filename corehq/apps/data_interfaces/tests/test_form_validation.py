from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.data_interfaces.forms import validate_case_property_name, is_valid_case_property_name
from django.core.exceptions import ValidationError
from django.test import TestCase


class TestFormValidation(TestCase):

    INVALID_PROPERTY_NAMES = [
        '  parent/abc ',
        '  host/abc ',
        'abc~',
        '  ',
        None,
    ]

    def test_validate_case_property_name_with_parent_case_references(self):
        self.assertEqual(
            validate_case_property_name('  abc ', allow_parent_case_references=True),
            'abc'
        )

        self.assertEqual(
            validate_case_property_name('  parent/abc ', allow_parent_case_references=True),
            'parent/abc'
        )

        self.assertEqual(
            validate_case_property_name('  host/abc ', allow_parent_case_references=True),
            'host/abc'
        )

        with self.assertRaises(ValidationError):
            validate_case_property_name('abc~', allow_parent_case_references=True)

        with self.assertRaises(ValidationError):
            validate_case_property_name('parent/abc~', allow_parent_case_references=True)

        with self.assertRaises(ValidationError):
            validate_case_property_name('  ', allow_parent_case_references=True)

        with self.assertRaises(ValidationError):
            validate_case_property_name(None, allow_parent_case_references=True)

        with self.assertRaises(ValidationError):
            validate_case_property_name('  parent/ ', allow_parent_case_references=True)

        with self.assertRaises(ValidationError):
            validate_case_property_name('unknown/abc', allow_parent_case_references=True)

    def test_validate_case_property_name_without_parent_case_references(self):
        self.assertEqual(
            validate_case_property_name('  abc ', allow_parent_case_references=False),
            'abc'
        )
        for invalid_property_name in self.INVALID_PROPERTY_NAMES:
            with self.assertRaises(ValidationError):
                validate_case_property_name(invalid_property_name, allow_parent_case_references=False)

    def test_is_valid_caes_property_name(self):
        for valid_property_name in ['abc', 'foo_bar']:
            self.assertTrue(is_valid_case_property_name(valid_property_name))

        for invalid_property_name in self.INVALID_PROPERTY_NAMES + [' abc ']:
            self.assertFalse(is_valid_case_property_name(invalid_property_name))
