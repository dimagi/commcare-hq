from django.test import TestCase, override_settings
from corehq.util.test_utils import flag_enabled
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition, CustomDataEditor
from corehq.apps.custom_data_fields.models import CustomDataField
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser, UserRole, Permissions
from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE, UserFieldsView
from corehq.apps.users.forms import UpdateCommCareUserInfoForm
from corehq.apps.users.signals import clean_commcare_user
from .utils import setup_enikshay_locations
from ..user_setup import get_allowable_usertypes, validate_nikshay_code, USER_TYPES


@flag_enabled('ENIKSHAY')
@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestUserSetupUtils(TestCase):
    domain = 'enikshay-user-setup'

    @classmethod
    def setUpClass(cls):
        super(TestUserSetupUtils, cls).setUpClass()
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()
        cls.location_types, cls.locations = setup_enikshay_locations(cls.domain)

        # set up data fields
        cls.user_fields = CustomDataFieldsDefinition.get_or_create(
            cls.domain, CUSTOM_USER_DATA_FIELD_TYPE)
        cls.user_fields.fields = [
            CustomDataField(slug='usertype', is_multiple_choice=True, choices=[ut.user_type for ut in USER_TYPES]),
            CustomDataField(slug='is_test'),
            CustomDataField(slug='nikshay_id'),
        ]
        cls.user_fields.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestUserSetupUtils, cls).tearDownClass()

    def assertValid(self, form):
        msg = "{} has errors: \n{}".format(form.__class__.__name__, form.errors.as_text())
        self.assertTrue(form.is_valid(), msg)

    def assertInvalid(self, form):
        msg = "{} has no errors".format(form.__class__.__name__)
        self.assertFalse(form.is_valid(), msg)

    def make_location(self, name, loc_type, parent):
        loc = SQLLocation.objects.create(
            domain=self.domain,
            name=name,
            site_code=name,
            location_type=self.location_types[loc_type],
            parent=self.locations[parent],
            metadata={'nikshay_code': name},
        )
        self.addCleanup(loc.delete)
        return loc

    def make_user(self, username, location):
        user = CommCareUser.create(
            self.domain,
            username,
            "123",
        )
        self.addCleanup(user.delete)
        user.set_location(self.locations[location])
        return user

    def test_get_allowable_usertypes(self):
        user = self.make_user('jon-snow@website', 'DTO')
        self.assertEqual(user.get_sql_location(self.domain).location_type.name, 'dto')
        self.assertEqual(get_allowable_usertypes(self.domain, user), ['dto', 'deo'])
        user.unset_location(self.domain)
        user.get_sql_location.reset_cache(user)
        user.set_location(self.locations['STO'])
        self.assertEqual(get_allowable_usertypes(self.domain, user), ['sto'])

    @mock.patch('custom.enikshay.user_setup.set_user_role', mock.MagicMock)
    def test_signal(self):
        # This test runs the whole callback via a signal as an integration test
        # To verify that it's working, it checks for errors triggered in `get_allowable_usertypes`
        user = self.make_user('atargaryon@nightswatch.onion', 'DTO')
        data = {
            'first_name': 'Aemon',
            'last_name': 'Targaryon',
            'language': '',
            'loadtest_factor': '',
            'role': '',
            'form_type': 'update-user',
            'email': 'atargaryon@nightswatch.onion',
            'data-field-usertype': ['tbhv'],  # invalid usertype
        }
        user_form = UpdateCommCareUserInfoForm(
            data=data,
            existing_user=user,
            domain=self.domain,
        )
        custom_data = CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            existing_custom_data=user.user_data,
            post_dict=data,
        )
        self.assertValid(user_form)
        self.assertValid(custom_data)
        clean_commcare_user.send(
            'BaseEditUserView.update_user',
            domain=self.domain,
            user=user,
            forms={'UpdateCommCareUserInfoForm': user_form,
                   'CustomDataEditor': custom_data}
        )
        self.assertValid(user_form)
        self.assertInvalid(custom_data)  # there should be an error

        data['data-field-usertype'] = 'dto'  # valid usertype
        form = UpdateCommCareUserInfoForm(
            data=data,
            existing_user=user,
            domain=self.domain,
        )
        self.assertValid(form)

    def test_validate_nikshay_code(self):
        loc1 = self.make_location('winterfell', 'tu', 'DTO')
        loc2 = self.make_location('castle_black', 'tu', 'DTO')
        self.assertTrue(validate_nikshay_code(self.domain, loc2))
        loc2.metadata['nikshay_code'] = loc1.metadata['nikshay_code']
        self.assertFalse(validate_nikshay_code(self.domain, loc2))
