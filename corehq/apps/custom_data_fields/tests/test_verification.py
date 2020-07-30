from django.test import SimpleTestCase

from corehq.apps.custom_data_fields.edit_model import CustomDataFieldsForm


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
