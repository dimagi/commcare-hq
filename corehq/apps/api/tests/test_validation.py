from django.test import TestCase
from unittest.mock import patch

from corehq.apps.api.validation import WebUserResourceValidator
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.util.test_utils import flag_enabled, flag_disabled
from corehq.apps.users.role_utils import initialize_domain_with_default_roles


class TestWebUserResourceValidator(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain(name="test-domain", is_active=True)
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)
        initialize_domain_with_default_roles(cls.domain.name)
        cls.requesting_user = WebUser.create(cls.domain.name, "test@example.com", "123", None, None)
        cls.requesting_user.set_role(cls.domain.name, 'admin')
        cls.requesting_user.save()
        cls.validator = WebUserResourceValidator(cls.domain.name, cls.requesting_user)

        cls.definition = CustomDataFieldsDefinition.get_or_create(cls.domain.name, UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='imaginary',
                label='Imaginary Person',
                choices=['yes', 'no'],
            ),
        ])
        cls.definition.save()
        cls.profile = CustomDataFieldsProfile(
            name='character',
            fields={'imaginary': 'yes'},
            definition=cls.definition,
        )
        cls.profile.save()

    @classmethod
    def tearDownClass(cls):
        cls.requesting_user.delete(None, None)
        super().tearDownClass()

    def test_simple_is_valid(self):
        data = {"email": "newtest@example.com", "role": "App Editor"}
        self.assertEqual(self.validator.is_valid(data, True), [])

    def test_validate_parameters(self):
        params = {"email": "test@example.com", "role": "Admin"}
        self.assertIsNone(self.validator.validate_parameters(params, True))

        params = {"email": "test@example.com", "role": "Admin"}
        self.assertEqual(self.validator.validate_parameters(params, False), "Invalid parameter(s): email")

        invalid_params = {"invalid_param": "value"}
        self.assertEqual(self.validator.validate_parameters(invalid_params, True),
                         "Invalid parameter(s): invalid_param")
        self.assertEqual(self.validator.validate_parameters(invalid_params, False),
                         "Invalid parameter(s): invalid_param")

    @flag_enabled('TABLEAU_USER_SYNCING')
    @patch('corehq.apps.users.models.WebUser.has_permission', return_value=True)
    def test_validate_parameters_with_tableau_edit_permission(self, mock_has_permission):
        params = {"email": "test@example.com", "role": "Admin", "tableau_role": "Viewer"}
        self.assertIsNone(self.validator.validate_parameters(params, True))

    @flag_disabled('TABLEAU_USER_SYNCING')
    @patch('corehq.apps.users.models.WebUser.has_permission', return_value=False)
    def test_validate_parameters_without_tableau_edit_permission(self, mock_has_permission):
        params = {"email": "test@example.com", "role": "Admin", "tableau_role": "Viewer"}
        self.assertEqual(self.validator.validate_parameters(params, True),
                         "You do not have permission to edit Tableau Configuration.")

    @patch('corehq.apps.registration.validation.domain_has_privilege', return_value=True)
    def test_validate_parameters_with_profile_permission(self, mock_domain_has_privilege):
        params = {"email": "test@example.com", "role": "Admin", "profile": "some_profile"}
        self.assertIsNone(self.validator.validate_parameters(params, True))

    @patch('corehq.apps.registration.validation.domain_has_privilege', return_value=False)
    def test_validate_parameters_without_profile_permission(self, mock_domain_has_privilege):
        params = {"email": "test@example.com", "role": "Admin", "profile": "some_profile"}
        self.assertEqual(self.validator.validate_parameters(params, True),
                         "This domain does not have user profile privileges.")

    @patch('corehq.apps.registration.validation.domain_has_privilege', return_value=True)
    def test_validate_parameters_with_location_privilege(self, mock_domain_has_privilege):
        params = {"email": "test@example.com", "role": "Admin", "primary_location_id": "some_location"}
        self.assertIsNone(self.validator.validate_parameters(params, True))
        params = {"email": "test@example.com", "role": "Admin", "assigned_location_ids": "some_location"}
        self.assertIsNone(self.validator.validate_parameters(params, True))

    @patch('corehq.apps.registration.validation.domain_has_privilege', return_value=False)
    def test_validate_parameters_without_location_privilege(self, mock_domain_has_privilege):
        params = {"email": "test@example.com", "role": "Admin", "primary_location_id": "some_location"}
        self.assertEqual(self.validator.validate_parameters(params, True),
                         "This domain does not have locations privileges.")

        params = {"email": "test@example.com", "role": "Admin", "assigned_location_ids": "some_location"}
        self.assertEqual(self.validator.validate_parameters(params, True),
                         "This domain does not have locations privileges.")

    def test_validate_role(self):
        self.assertIsNone(self.validator.validate_role("App Editor"))
        self.assertEqual(self.validator.validate_role("Fake Role"),
                         "Role 'Fake Role' does not exist or you do not have permission to access it")

    def test_validate_role_with_no_role_input(self):
        self.assertIsNone(self.validator.validate_role(None))

    def test_validate_profile_with_no_profile_input(self):
        self.definition.profile_required_for_user_type = [UserFieldsView.WEB_USER]
        self.definition.save()
        self.assertIsNone(self.validator.validate_profile(None, False))
        self.assertEqual(self.validator.validate_profile(None, True),
            "A profile must be assigned to users of the following type(s): Web Users")
        self.definition.profile_required_for_user_type = []
        self.definition.save()

    def test_validate_profile_with_conflicting_user_data(self):
        self.assertEqual(self.validator.validate_custom_data_with_profile({'imaginary': 'yes'}, 'character'),
            ["'imaginary' cannot be set directly"])

    def test_validate_email(self):
        self.assertIsNone(self.validator.validate_email("newtest@example.com", True))

        self.assertEqual(self.validator.validate_email("test@example.com", True),
                        "A user with this email address is already in "
                        "this project or has a pending invitation.")

        deactivated_user = WebUser.create(self.domain.name, "deactivated@example.com", "123", None, None)
        deactivated_user.is_active = False
        deactivated_user.save()
        self.assertEqual(self.validator.validate_email("deactivated@example.com", True),
                         "A user with this email address is deactivated. ")

    def test_validate_email_with_no_email_input(self):
        self.assertIsNone(self.validator.validate_email(None, True))

    def test_validate_locations(self):
        self.assertIsNone(self.validator.validate_locations(self.requesting_user.username,
                                                            None, None))
        self.assertEqual(
            self.validator.validate_locations(self.requesting_user.username, ["loc1", "loc2"], None),
            "Both primary_location and locations must be provided together."
        )
        self.assertEqual(
            self.validator.validate_locations(self.requesting_user.username, None, 'loc1'),
            "Both primary_location and locations must be provided together."
        )

        with patch(
            'corehq.apps.user_importer.validation.LocationValidator.validate_location_ids'
        ) as mock_validate_location_ids:
            mock_validate_location_ids.return_value = None
            self.assertIsNone(self.validator.validate_locations(self.requesting_user.username,
                                                                ["loc1", "loc2"], "loc1"))

            user_result = mock_validate_location_ids.call_args[0][0]
            self.assertEqual(user_result.editable_user.username, self.requesting_user.username)
            location_ids = mock_validate_location_ids.call_args[0][1]
            self.assertCountEqual(location_ids, ["loc1", "loc2"])

        self.assertEqual(
            self.validator.validate_locations(self.requesting_user.username, ["loc1", "loc2"], "loc3"),
            "Primary location must be one of the user's locations"
        )

        self.assertEqual(
            self.validator.validate_locations(self.requesting_user.username, ["loc1", "loc2"], ""),
            "Primary location can't be empty if the user has any locations set"
        )
