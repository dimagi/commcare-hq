from __future__ import absolute_import
from datetime import datetime
import mock
import uuid
from django.test import TestCase, override_settings
from corehq.util.test_utils import flag_enabled
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition, CustomDataEditor
from corehq.apps.custom_data_fields.models import CustomDataField
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.users.models import CommCareUser, WebUser, UserRole, Permissions
from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE, UserFieldsView
from corehq.apps.users.forms import UpdateCommCareUserInfoForm
from corehq.apps.users.util import format_username, update_device_meta
from .utils import setup_enikshay_locations
from ..const import (
    DEFAULT_MOBILE_WORKER_ROLE,
    PRIVATE_SECTOR_WORKER_ROLE,
    AGENCY_LOCATION_TYPES,
    AGENCY_LOCATION_FIELDS,
    AGENCY_USER_FIELDS,
)
from ..user_setup import (
    LOC_TYPES_TO_USER_TYPES,
    validate_usertype,
    get_site_code,
    ENikshayLocationFormSet,
    compress_nikshay_id,
    get_new_username_and_id,
    set_enikshay_device_id,
)
from ..models import IssuerId


@flag_enabled('ENIKSHAY')
@mock.patch('custom.enikshay.user_setup.skip_custom_setup', lambda *args: False)
@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestUserSetupUtils(TestCase):
    domain = 'enikshay-user-setup'

    @classmethod
    def setUpClass(cls):
        super(TestUserSetupUtils, cls).setUpClass()
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()
        cls.location_types, cls.locations = setup_enikshay_locations(cls.domain)

        with mock.patch('corehq.apps.locations.tasks._create_or_unarchive_users', mock.MagicMock()):
            for location_type in cls.location_types.values():
                if location_type.code in AGENCY_LOCATION_TYPES:
                    location_type.has_user = True
                    location_type.save()

        # set up data fields
        user_fields = CustomDataFieldsDefinition.get_or_create(
            cls.domain, CUSTOM_USER_DATA_FIELD_TYPE)

        usertypes = [t for types in LOC_TYPES_TO_USER_TYPES.values() for t in types]
        user_fields.fields = [
            CustomDataField(slug='usertype', is_multiple_choice=True, choices=usertypes),
            CustomDataField(slug='is_test'),
            CustomDataField(slug='nikshay_id'),
        ] + [
            CustomDataField(slug=slug, is_required=False) for slug, _, __ in AGENCY_USER_FIELDS
        ]
        user_fields.save()

        location_fields = CustomDataFieldsDefinition.get_or_create(
            cls.domain, LocationFieldsView.field_type)
        location_fields.fields = [
            CustomDataField(slug='nikshay_code', is_required=True)
        ] + [
            CustomDataField(slug=slug) for slug, _, __ in AGENCY_LOCATION_FIELDS
        ]
        location_fields.save()

        cls.web_user = WebUser.create(cls.domain, 'blah', 'password')

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        cls.web_user.delete()
        IssuerId.objects.all().delete()
        super(TestUserSetupUtils, cls).tearDownClass()

    def assertValid(self, form):
        if isinstance(form, ENikshayLocationFormSet):
            errors = ", ".join([_f for _f in [f.errors.as_text() for f in form.forms] if _f])
        else:
            errors = form.errors.as_text()
        msg = "{} has errors: \n{}".format(form.__class__.__name__, errors)
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

    def _get_form_bound_data(self, location_name, location_type, location_fields, user_fields):
        user_fields = {} if user_fields is None else user_fields
        location_fields = {} if location_fields is None else location_fields

        bound_data = {
            "location_type": location_type,
            "name": location_name,
            "location_user-password": "1234",
            "form_type": "location-settings",
        }

        if location_type in AGENCY_LOCATION_TYPES:
            for slug, _, __ in AGENCY_USER_FIELDS:
                value = user_fields.get(slug, "")
                if slug == 'contact_phone_number' and value == "":
                    value = "911234567890"
                if slug == 'language_code' and value == "":
                    value = "hin"
                bound_data['user_data-{}'.format(slug)] = value

        for slug, _, __ in [('nikshay_code', '', '')] + AGENCY_LOCATION_FIELDS:
            value = location_fields.get(slug, "")
            if slug == 'nikshay_code' and value == "":
                value = uuid.uuid4().hex
            bound_data['data-field-{}'.format(slug)] = value

        return bound_data

    def make_new_location_form(self, location_name, location_type, parent, location_fields=None, user_fields=None):
        bound_data = self._get_form_bound_data(location_name, location_type, location_fields, user_fields)
        return ENikshayLocationFormSet(
            location=SQLLocation(domain=self.domain, parent=parent),
            bound_data=bound_data,
            request_user=self.web_user,
            is_new=True,
        )

    def test_validate_usertype(self):
        user = self.make_user('jon-snow@website', 'DTO')
        loc_type = self.location_types['dto'].code

        # Try submitting an invalid usertype
        custom_data = CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            existing_custom_data=user.user_data,
            post_dict={'data-field-usertype': ['sto']},
        )
        validate_usertype(loc_type, 'sto', custom_data)
        self.assertInvalid(custom_data)

        # Try submitting a valid usertype
        custom_data = CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            existing_custom_data=user.user_data,
            post_dict={'data-field-usertype': ['deo']},  # invalid usertype
        )
        validate_usertype(loc_type, 'deo', custom_data)
        self.assertValid(custom_data)

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
        # TODO update this test to account for form subclasses
        # self.assertValid(user_form)
        # self.assertInvalid(custom_data)  # there should be an error

        # data['data-field-usertype'] = 'dto'  # valid usertype
        # form = UpdateCommCareUserInfoForm(
        #     data=data,
        #     existing_user=user,
        #     domain=self.domain,
        # )
        # self.assertValid(form)

    def test_validate_nikshay_code(self):
        parent = self.locations['CTO']
        form = self.make_new_location_form('winterfell', 'dto', parent=parent,
                                           location_fields={'nikshay_code': '123'})
        self.assertValid(form)
        form.save()

        # Making a new location with the same parent and nikshay_code should fail
        form = self.make_new_location_form('castle_black', 'dto', parent=parent,
                                           location_fields={'nikshay_code': '123'})
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
        set_enikshay_device_id(user, 'blackberry')
        user.save()
        self.assertEqual(user.user_data['id_device_number'], 3)

        # Oberyn uses the palm-pilot again, which was device #2
        update_device_meta(user, 'palm-pilot')
        self.assertEqual(user.user_data['id_device_number'], 2)

    def test_device_id_same_day(self):
        user = self.make_user('redviper@martell.biz', 'DTO')
        update_device_meta(user, 'rotary')
        update_device_meta(user, 'palm-pilot')
        update_device_meta(user, 'blackberry')
        palm_pilot_last_used_1 = [device.last_used for device in user.devices
                                  if device.device_id == 'palm-pilot'][0]
        self.assertEqual(user.user_data['id_device_number'], 3)

        # Updating the device ID a second time in the same day doesn't change
        # the entry in user.devices, but it SHOULD update the enikshay user data
        update_device_meta(user, 'palm-pilot')
        palm_pilot_last_used_2 = [device.last_used for device in user.devices
                                  if device.device_id == 'palm-pilot'][0]
        self.assertEqual(palm_pilot_last_used_1, palm_pilot_last_used_2)
        user = CommCareUser.get(user._id)  # make sure it's set in the DB
        self.assertEqual(user.user_data['id_device_number'], 2)

    def test_add_drtb_hiv_to_dto(self):
        ellaria = self.make_user('esand@martell.biz', 'DRTB-HIV')
        self.assertEqual(ellaria.location_id, self.locations['DRTB-HIV'].location_id)
        self.assertItemsEqual(
            [l.name for l in ellaria.get_sql_locations(self.domain)],
            [self.locations['DRTB-HIV'].name, self.locations['DTO'].name]
        )

    def test_get_site_code(self):
        for expected, name, nikshay_code, type_code, parent in [
            ('sto_nikshaycode', 'mysto', 'nikshaycode', 'sto', self.locations['CTD']),
            ('cdst_nikshaycode', 'mycdst', 'nikshaycode', 'cdst', self.locations['STO']),
            ('cto_sto_mycto', 'mycto', 'nikshaycode', 'cto', self.locations['STO']),
            ('drtbhiv_dto', 'mydrtb-hiv', 'nikshaycode', 'drtb-hiv', self.locations['DTO']),
            ('dto_cto_nikshaycode', 'mydto', 'nikshaycode', 'dto', self.locations['CTO']),
            ('tu_dto_nikshaycode', 'mytu', 'nikshaycode', 'tu', self.locations['DTO']),
            ('phi_tu_nikshaycode', 'myphi', 'nikshaycode', 'phi', self.locations['TU']),
            ('dmc_tu_nikshaycode', 'mydmc', 'nikshaycode', 'dmc', self.locations['TU']),

            # remove spaces and lowercase from nikshay code
            ('cdst_nikshay_code', 'mycdst', 'Nikshay Code', 'cdst', self.locations['STO']),
            # single digit integer nikshay codes get prefixed with 0
            ('cdst_01', 'mycdst', '1', 'cdst', self.locations['STO']),
            # make name a slug
            ('cto_sto_cra-z_nm3', 'cRa-Z n@m3', 'nikshaycode', 'cto', self.locations['STO']),
        ]:
            self.assertEqual(expected, get_site_code(name, nikshay_code, type_code, parent))

    def test_conflicting_username(self):
        def id_to_username(issuer_id):
            return format_username(compress_nikshay_id(issuer_id, 3), self.domain)

        # Figure out what the next issuer_id should be, and create a user with that username
        issuer_id, _ = IssuerId.objects.get_or_create(domain=self.domain, user_id='some_id')
        starting_count = IssuerId.objects.count()
        username = id_to_username(issuer_id.pk + 1)
        CommCareUser.create(self.domain, username, '123')

        # Creating a new username should skip over that manually created user to avoid id conflicts
        username, user_id = get_new_username_and_id(self.domain)
        self.assertEqual(username, id_to_username(issuer_id.pk + 2))

        # Two IssuerId objects should have been created - a real one and one for the bad, manual user
        self.assertEqual(IssuerId.objects.count(), starting_count + 2)

    def test_set_default_role(self):
        self.make_role(DEFAULT_MOBILE_WORKER_ROLE)
        user = self.make_user('redviper@martell.biz', 'DTO')
        self.assertEqual(DEFAULT_MOBILE_WORKER_ROLE, user.get_role(self.domain).name)

        # you should be able to unset (or change) the role later
        user.set_role(self.domain, 'none')
        user.save()
        self.assertFalse(user.get_role(self.domain))

    def test_set_default_agency_role(self):
        self.make_role(PRIVATE_SECTOR_WORKER_ROLE)
        parent = self.locations['DTO']
        form = self.make_new_location_form('sept_of_baelor', 'pcp', parent=parent)
        self.assertValid(form)
        form.save()
        self.assertEqual("Private Sector Worker", form.user.get_role(self.domain).name)
