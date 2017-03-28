import mock
from datetime import datetime
from django.test import TestCase, override_settings
from corehq.util.test_utils import flag_enabled
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition, CustomDataEditor
from corehq.apps.custom_data_fields.models import CustomDataField
from corehq.apps.domain.models import Domain
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.users.models import CommCareUser, WebUser, UserRole, Permissions
from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE, UserFieldsView
from corehq.apps.users.forms import UpdateCommCareUserInfoForm
from corehq.apps.users.signals import clean_commcare_user
from .utils import setup_enikshay_locations
from ..user_setup import validate_nikshay_code, LOC_TYPES_TO_USER_TYPES, set_user_role, validate_usertype
from ..models import IssuerId


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
        user_fields = CustomDataFieldsDefinition.get_or_create(
            cls.domain, CUSTOM_USER_DATA_FIELD_TYPE)

        usertypes = [t for types in LOC_TYPES_TO_USER_TYPES.values() for t in types]
        user_fields.fields = [
            CustomDataField(slug='usertype', is_multiple_choice=True, choices=usertypes),
            CustomDataField(slug='is_test'),
            CustomDataField(slug='nikshay_id'),
        ]
        user_fields.save()

        location_fields = CustomDataFieldsDefinition.get_or_create(
            cls.domain, LocationFieldsView.field_type)
        location_fields.fields = [CustomDataField(slug='nikshay_code', is_required=True)]
        location_fields.save()

        cls.web_user = WebUser.create(cls.domain, 'blah', 'password')

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        cls.web_user.delete()
        IssuerId.objects.all().delete()
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

    def make_role(self, name):
        role = UserRole(
            domain=self.domain,
            name=name,
            permissions=Permissions(),
        )
        role.save()
        self.addCleanup(role.delete)

    def make_new_location_form(self, name, parent, nikshay_code):
        return LocationForm(
            location=SQLLocation(domain=self.domain, parent=parent),
            bound_data={'name': name,
                  'data-field-nikshay_code': nikshay_code},
            user=self.web_user,
            is_new=True,
        )

    def make_edit_location_form(self, location, data):
        bound_data = {
            'name': location.name,
            'site_code': location.site_code,
            'data-field-nikshay_code': location.metadata.get('nikshay_code'),
            'coordinates': '',
            'parent_id': '',
            'external_id': '',
            'location_type': location.location_type.code,
        }
        bound_data.update(data)
        return LocationForm(
            location=None,
            bound_data=bound_data,
            user=self.web_user,
            is_new=False,
        )

    def test_validate_usertype(self):
        user = self.make_user('jon-snow@website', 'DTO')
        loc = self.locations['DTO']

        # Try submitting an invalid usertype
        custom_data = CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            existing_custom_data=user.user_data,
            post_dict={'data-field-usertype': ['sto']},
        )
        validate_usertype(self.domain, loc, 'sto', custom_data)
        self.assertInvalid(custom_data)

        # Try submitting a valid usertype
        custom_data = CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            existing_custom_data=user.user_data,
            post_dict={'data-field-usertype': ['deo']},  # invalid usertype
        )
        validate_usertype(self.domain, loc, 'deo', custom_data)
        self.assertValid(custom_data)

    @mock.patch('custom.enikshay.user_setup.set_user_role', mock.MagicMock)
    def test_signal(self):
        # This test runs the whole callback via a signal as an integration test
        # To verify that it's working, it checks for errors triggered in `validate_usertype`
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
            request_user=self.web_user,
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

    def test_set_user_role(self):
        user = self.make_user('lordcommander@nightswatch.onion', 'DTO')
        data = {
            'first_name': 'Jeor',
            'last_name': 'Mormont',
            'language': '',
            'loadtest_factor': '',
            'role': '',
            'form_type': 'update-user',
            'email': 'lordcommander@nightswatch.onion',
        }
        user_form = UpdateCommCareUserInfoForm(
            data=data,
            existing_user=user,
            domain=self.domain,
        )
        self.assertValid(user_form)
        set_user_role(self.domain, user, 'dto', user_form)
        # The corresponding role doesn't exist yet!
        self.assertInvalid(user_form)

        self.make_role('dto')
        user_form = UpdateCommCareUserInfoForm(
            data=data,
            existing_user=user,
            domain=self.domain,
        )
        self.assertValid(user_form)
        set_user_role(self.domain, user, 'dto', user_form)
        self.assertValid(user_form)

    def test_validate_nikshay_code(self):
        parent = self.locations['CTO']
        form = self.make_new_location_form('winterfell', parent=parent, nikshay_code='123')
        self.assertValid(form)
        validate_nikshay_code(self.domain, form)
        self.assertValid(form)
        form.save()

        # Making a new location with the same parent and nikshay_code should fail
        form = self.make_new_location_form('castle_black', parent=parent, nikshay_code='123')
        self.assertValid(form)
        validate_nikshay_code(self.domain, form)
        self.assertInvalid(form)

    def test_issuer_id(self):
        areo = self.make_user('ahotah@martell.biz', 'DTO')
        areo_number = areo.user_data['id_issuer_number']
        self.assertTrue(areo_number)

        # the next id should be 1 more than this ID
        arys = self.make_user('aoakheart@kingsguard.gov', 'DTO')
        self.assertTrue(areo_number + 1 == arys.user_data['id_issuer_number'])

    def test_device_id(self):
        user = self.make_user('redviper@martell.biz', 'DTO')
        user.update_device_id_last_used('rotary', datetime(1984, 1, 1))
        user.update_device_id_last_used('palm-pilot', datetime(1997, 1, 1))
        user.update_device_id_last_used('blackberry', datetime(2008, 1, 1))
        user.save()
        self.assertEqual(user.user_data['id_device_number'], 3)

        # Oberyn uses the palm-pilot again, which was device #2
        user.update_device_id_last_used('palm-pilot', datetime(2017, 1, 1))
        user.save()
        self.assertEqual(user.user_data['id_device_number'], 2)


    def test_add_drtb_hiv_to_dto(self):
        ellaria = self.make_user('esand@martell.biz', 'DRTB-HIV')
        self.assertEqual(ellaria.location_id, self.locations['DRTB-HIV'].location_id)
        self.assertItemsEqual(
            [l.name for l in ellaria.get_sql_locations(self.domain)],
            [self.locations['DRTB-HIV'].name, self.locations['DTO'].name]
        )
