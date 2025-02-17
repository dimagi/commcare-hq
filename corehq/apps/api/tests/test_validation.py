from django.test import TestCase
from unittest.mock import patch

from corehq.apps.api.validation import WebUserResourceSpec, WebUserValidationException
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

    def setUp(self):
        self.spec = WebUserResourceSpec(
            domain=self.domain.name,
            requesting_user=self.requesting_user,
            email="newtest@example.com",
        )

    def test_validate_parameters(self):
        self.spec.is_post = True
        self.spec.parameters = ["email", "role"]

        with self.assertRaises(WebUserValidationException) as e:
            self.spec.parameters = ["invalid_param"]
        self.assertEqual(e.exception.message, ["Invalid parameter(s): invalid_param"])

        self.spec.is_post = False
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.parameters = ["email", "role"]
        self.assertEqual(e.exception.message, ["Invalid parameter(s): email"])

        with self.assertRaises(WebUserValidationException) as e:
            self.spec.parameters = ["invalid_param"]
        self.assertEqual(e.exception.message, ["Invalid parameter(s): invalid_param"])

    @flag_enabled('TABLEAU_USER_SYNCING')
    @patch('corehq.apps.users.models.WebUser.has_permission', return_value=True)
    def test_validate_parameters_with_tableau_edit_permission(self, mock_has_permission):
        self.spec.parameters = ["tableau_role"]

    @flag_disabled('TABLEAU_USER_SYNCING')
    @patch('corehq.apps.users.models.WebUser.has_permission', return_value=False)
    def test_validate_parameters_without_tableau_edit_permission(self, mock_has_permission):
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.parameters = ["tableau_role"]
        self.assertEqual(e.exception.message, ['You do not have permission to edit Tableau Configuration.'])

    @patch('corehq.apps.api.validation.domain_has_privilege', return_value=True)
    def test_validate_parameters_with_profile_permission(self, mock_domain_has_privilege):
        self.spec.parameters = ["profile"]

    @patch('corehq.apps.api.validation.domain_has_privilege', return_value=False)
    def test_validate_parameters_without_profile_permission(self, mock_domain_has_privilege):
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.parameters = ["profile"]
        self.assertEqual(e.exception.message, ['This domain does not have user profile privileges.'])

    @patch('corehq.apps.api.validation.domain_has_privilege', return_value=True)
    def test_validate_parameters_with_location_privilege(self, mock_domain_has_privilege):
        self.spec.parameters = ["primary_location_id"]
        self.spec.parameters = ["assigned_location_ids"]

    @patch('corehq.apps.api.validation.domain_has_privilege', return_value=False)
    def test_validate_parameters_without_location_privilege(self, mock_domain_has_privilege):
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.parameters = ["primary_location_id"]
        self.assertEqual(e.exception.message, ['This domain does not have locations privileges.'])

        with self.assertRaises(WebUserValidationException) as e:
            self.spec.parameters = ["assigned_location_ids"]
        self.assertEqual(e.exception.message, ['This domain does not have locations privileges.'])

    def test_validate_role(self):
        self.spec.role = "App Editor"
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.role = "Fake Role"
        self.assertEqual(e.exception.message,
                         ["Role 'Fake Role' does not exist or you do not have permission to access it"])

    def test_validate_profile_with_no_profile_input(self):
        self.definition.profile_required_for_user_type = [UserFieldsView.WEB_USER]
        self.definition.save()
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.new_or_existing_profile_name = None
        self.assertEqual(e.exception.message,
                         ['A profile must be assigned to users of the following type(s): Web Users'])
        self.definition.profile_required_for_user_type = []
        self.definition.save()
        self.spec.new_or_existing_profile_name = None

    def test_validate_profile_with_conflicting_user_data(self):
        self.spec.new_or_existing_profile_name = 'character'
        self.spec.new_or_existing_user_data = {'imaginary': 'yes'}

        with self.assertRaises(WebUserValidationException) as e:
            self.spec.new_or_existing_user_data = {'imaginary': 'no'}
        self.assertEqual(e.exception.message, ["'imaginary' is defined by the profile so cannot be set directly"])

    def test_validate_email(self):
        self.spec.email = "newtest@example.com"

        self.spec.is_post = True
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.email = "test@example.com"
        self.assertEqual(e.exception.message,
                        ['A user with this email address is already in '
                        'this project or has a pending invitation.'])

        deactivated_user = WebUser.create(self.domain.name, "deactivated@example.com", "123", None, None)
        deactivated_user.is_active = False
        deactivated_user.save()
        with self.assertRaises(WebUserValidationException) as e:
            self.spec.email = "deactivated@example.com"
        self.assertEqual(e.exception.message, ['A user with this email address is deactivated. '])

    def test_validate_locations(self):
        self.spec.primary_location_id = None
        self.spec.assigned_location_ids = None

        with self.assertRaises(WebUserValidationException) as e:
            self.spec.primary_location_id = "loc1"
        self.assertEqual(e.exception.message, ["Both primary_location and locations must be provided together."])

        with self.assertRaises(WebUserValidationException) as e:
            self.spec.assigned_location_ids = ["loc1", "loc2"]
        self.assertEqual(e.exception.message, ["Both primary_location and locations must be provided together."])

        with patch(
            'corehq.apps.user_importer.validation.LocationValidator.validate_location_ids'
        ) as mock_validate_location_ids:
            mock_validate_location_ids.return_value = None
            spec = WebUserResourceSpec(
                domain=self.domain.name,
                requesting_user=self.requesting_user,
                email=self.requesting_user.username,
                primary_location_id="loc1",
                assigned_location_ids=["loc1", "loc2"],
            )

            user_result = mock_validate_location_ids.call_args[0][0]
            self.assertEqual(user_result.editable_user.username, self.requesting_user.username)
            location_ids = mock_validate_location_ids.call_args[0][1]
            self.assertCountEqual(location_ids, ["loc1", "loc2"])

        with self.assertRaises(WebUserValidationException) as e:
            spec.primary_location_id = "loc3"
        self.assertEqual(e.exception.message,
                         ["Primary location must be one of the user's locations"])

        with self.assertRaises(WebUserValidationException) as e:
            spec.primary_location_id = ""
        self.assertEqual(e.exception.message,
                         ["Primary location can't be empty if the user has any locations set"])
