from django.test import SimpleTestCase

from corehq.apps.custom_data_fields.models import Field

from corehq.apps.users.views.mobile.custom_data_fields import (
    WebUserFieldsView,
    CommcareUserFieldsView,
    UserFieldsView
)
from corehq.apps.locations.views import LocationFieldsView


class TestCustomDataFieldsFields(SimpleTestCase):
    def test_validate_required(self):
        required_field = Field(
            slug='favorite_chordata',
            is_required=True,
            label='Favorite Chordata',
        )
        self.assertIsNone(required_field.validate_required('sea lamprey'))
        self.assertEqual(required_field.validate_required(None), 'Favorite Chordata is required.')

        optional_field = Field(
            slug='fav_echinoderm',
            is_required=False,
            label='Favorite Echinoderm',
        )
        self.assertIsNone(optional_field.validate_required('sea cucumber'))
        self.assertIsNone(optional_field.validate_required(None))

    def test_web_user_required_field(self):
        web_user_required_field = Field(
            slug='web_user_field',
            is_required=True,
            required_for=[UserFieldsView.WEB_USER],
            label='Web User Field',
        )
        self.assertTrue(WebUserFieldsView.is_field_required(web_user_required_field))
        self.assertFalse(CommcareUserFieldsView.is_field_required(web_user_required_field))

    def test_commcare_user_required_field(self):
        commcare_user_required_field = Field(
            slug='commcare_user_field',
            is_required=True,
            required_for=[UserFieldsView.COMMCARE_USER],
            label='Commcare User Field',
        )
        self.assertTrue(CommcareUserFieldsView.is_field_required(commcare_user_required_field))
        self.assertFalse(WebUserFieldsView.is_field_required(commcare_user_required_field))

    def test_commcare_and_web_user_required_field(self):
        commcare_and_web_user_required_field = Field(
            slug='commcare_and_web_user_field',
            is_required=True,
            required_for=[UserFieldsView.COMMCARE_USER, UserFieldsView.WEB_USER],
            label='Commcare and Web User Field',
        )
        self.assertTrue(WebUserFieldsView.is_field_required(commcare_and_web_user_required_field))
        self.assertTrue(CommcareUserFieldsView.is_field_required(commcare_and_web_user_required_field))

    def test_location_required_field(self):
        location_required_field = Field(
            slug='location_field',
            is_required=True,
            required_for=[],
            label='Location Field',
        )
        self.assertTrue(LocationFieldsView.is_field_required(location_required_field))

    def test_validate_choices(self):
        field = Field(
            slug='warm_color',
            label='Warm Color',
            choices=[
                'red',
                'orange',
                'yellow',
            ],
        )
        self.assertIsNone(field.validate_choices('orange'))
        self.assertEqual(
            field.validate_choices('squishy'),
            "'squishy' is not a valid choice for Warm Color. The available options are: red, orange, yellow."
        )

    def test_validate_regex(self):
        field = Field(
            slug='s_word',
            label='Word starting with the letter S',
            regex='^[Ss]',
            regex_msg='That does not start with S',
        )
        self.assertIsNone(field.validate_regex('sibilant'))
        self.assertEqual(
            field.validate_regex('whisper'),
            "'whisper' is not a valid match for Word starting with the letter S"
        )
