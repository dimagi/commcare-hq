import pytest
from django.test import SimpleTestCase

from corehq.apps.custom_data_fields.edit_model import CustomDataFieldForm, CustomDataFieldsForm


class TestCustomDataFieldsVerification(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = [{
            "slug": "_type",
            "is_required": True,
            "label": "Type",
            "choices": ["autobot", "decepticon", "dinobot"],
        }, {
            "slug": "food",
            "is_required": False,
            "label": "Food",
            "regex": "soup$",
            "regex_msg": "This should end with soup",
        }]

        cls.profile = {
            "name": "grimlock",
            "fields": '{"_type": "dinobot", "food": "leaf soup"}',
        }

    def test_no_duplicates(self):
        self.assertEqual(set(), CustomDataFieldsForm.verify_no_duplicates(self.fields))
        self.assertEqual(
            {"Key 'food' was duplicated, key names must be unique."},
            CustomDataFieldsForm.verify_no_duplicates(self.fields + [{
                "slug": "food",
                "label": "Drink",
            }])
        )

    def test_no_duplicate_profiles(self):
        self.assertEqual(set(), CustomDataFieldsForm.verify_no_duplicate_profiles([self.profile]))
        self.assertEqual(
            {"Profile name 'grimlock' appears more than once. Profile names must be unique."},
            CustomDataFieldsForm.verify_no_duplicate_profiles([self.profile, {
                "name": "grimlock",
                "fields": '{"_type": "autobot", "color": "grey"}',
            }])
        )

    def test_no_reserved_words(self):
        self.assertEqual(set(), CustomDataFieldsForm.verify_no_reserved_words(self.fields))
        self.assertEqual(
            {"Key 'type' is a reserved word in Commcare."},
            CustomDataFieldsForm.verify_no_reserved_words([{
                "slug": "type",
                "choices": ["autobot", "decepticon", "dinobot"],
            }])
        )

    def test_no_profiles_missing_fields(self):
        self.assertEqual(set(), CustomDataFieldsForm.verify_no_profiles_missing_fields(self.fields,
                                                                                       [self.profile]))
        self.assertEqual(
            {"Profile 'grimlock' contains 'color' which is not a known field."},
            CustomDataFieldsForm.verify_no_profiles_missing_fields(self.fields, [{
                "name": "grimlock",
                "fields": '{"_type": "dinobot", "color": "grey"}',
            }])
        )

    def test_profiles_validate(self):
        self.assertEqual(set(), CustomDataFieldsForm.verify_profiles_validate(self.fields, [self.profile]))
        self.assertEqual(
            {"'cake' is not a valid match for Food"},
            CustomDataFieldsForm.verify_profiles_validate(self.fields, [{
                "name": "grimlock",
                "fields": '{"food": "cake"}',
            }])
        )


@pytest.mark.parametrize("key, value, error", [
    ('label', 'x' * 256, 'Labels must be at most 255 characters.'),
    ('slug', 'x' * 128, 'Property names must be at most 127 characters.'),
    ('regex_msg', 'x' * 256, 'Regex error messages must be at most 255 characters.'),
    ('regex', 'x' * 128, 'Regular expressions must be at most 127 characters (this one has 128).'),
])
def test_field_form_rejects_values_too_long_for_db(key, value, error):
    raw = {'slug': 'sector', 'label': 'Sector', key: value}
    form = CustomDataFieldForm(raw)
    assert not form.is_valid()
    assert form.errors[key] == [error]


@pytest.mark.parametrize("key, value", [
    ('label', 'x' * 255),
    ('slug', 'x' * 127),
    ('regex_msg', 'x' * 255),
    ('regex', 'x' * 127),
])
def test_field_form_accepts_values_at_limit(key, value):
    raw = {'slug': 'sector', 'label': 'Sector', key: value}
    form = CustomDataFieldForm(raw)
    assert form.is_valid(), form.errors
