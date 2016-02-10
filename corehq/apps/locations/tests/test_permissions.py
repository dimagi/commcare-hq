import random
import string

from corehq.apps.users.models import WebUser, CommCareUser
from corehq.toggles import (RESTRICT_FORM_EDIT_BY_LOCATION, NAMESPACE_DOMAIN)
from corehq.util.test_utils import flag_enabled
from couchforms.models import XFormInstance

from ..permissions import can_edit_form_location
from .util import LocationHierarchyTestCase


class TestPermissions(LocationHierarchyTestCase):
    location_type_names = ['state', 'county', 'city']
    stock_tracking_types = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
                ('Brookline', []),
            ])
        ])
    ]

    def test_can_edit_form_in_county(self):
        self.assertCanEdit(self.middlesex_web_user, self.cambridge_form)

    def test_cant_edit_out_of_county(self):
        self.assertCannotEdit(self.middlesex_web_user, self.boston_form)

    def test_can_edit_any_form(self):
        self.assertCanEdit(self.massachusetts_web_user, self.cambridge_form)
        self.assertCanEdit(self.massachusetts_web_user, self.boston_form)

    def test_project_admin_can_edit_anything(self):
        project_admin = WebUser.create(self.domain, 'kennedy', 'password')
        project_admin.get_domain_membership(self.domain).is_admin = True
        project_admin.save()

        self.assertCanEdit(project_admin, self.cambridge_form)
        self.assertCanEdit(project_admin, self.boston_form)

    def test_unassigned_web_user_cant_edit_anything(self):
        locationless_web_user = WebUser.create(self.domain, 'joeshmoe', 'password')
        self.assertCannotEdit(locationless_web_user, self.cambridge_form)
        self.assertCannotEdit(locationless_web_user, self.boston_form)

    @flag_enabled('MULTIPLE_LOCATIONS_PER_USER')
    def test_multiple_locations_per_user(self):
        # Note also that location types must not be administrative for multiple
        # locations per domain to work.  This was a pain to figure out...
        multi_loc_user = self.make_mobile_user('Cambridge')
        multi_loc_user.set_location(self.locations['Boston'].couch_location)
        multi_loc_form = self.make_form(multi_loc_user)

        self.assertCanEdit(self.middlesex_web_user, multi_loc_form)
        self.assertCanEdit(self.massachusetts_web_user, multi_loc_form)

    #### The rest of this class is helper methods and setup ####

    @classmethod
    def make_web_user(cls, location):
        username = ''.join(random.sample(string.letters, 8))
        user = WebUser.create(cls.domain, username, 'password')
        user.set_location(cls.domain, cls.locations[location].couch_location)
        return user

    @classmethod
    def make_mobile_user(cls, location):
        username = ''.join(random.sample(string.letters, 8))
        user = CommCareUser.create(cls.domain, username, 'password')
        user.set_location(cls.locations[location].couch_location)
        return user

    @classmethod
    def make_form(cls, mobile_user):
        return XFormInstance(
            domain=cls.domain,
            form={
                'meta': {'userID': mobile_user._id},
            },
        )

    @classmethod
    def setUpClass(cls):
        super(cls, TestPermissions).setUpClass()
        # enable feature flag
        RESTRICT_FORM_EDIT_BY_LOCATION.set(cls.domain, True, NAMESPACE_DOMAIN)
        # check checkbox
        cls.domain_obj.location_restriction_for_users = True
        cls.domain_obj.save()

        cls.middlesex_web_user = cls.make_web_user('Middlesex')
        cls.massachusetts_web_user = cls.make_web_user('Massachusetts')

        cambridge_user = cls.make_mobile_user('Cambridge')
        cls.cambridge_form = cls.make_form(cambridge_user)

        boston_user = cls.make_mobile_user('Boston')
        cls.boston_form = cls.make_form(boston_user)

    def assertCanEdit(self, user, form):
        msg = "This user CANNOT edit this form!"
        self.assertTrue(can_edit_form_location(self.domain, user, form), msg=msg)

    def assertCannotEdit(self, user, form):
        msg = "This user CAN edit this form!"
        self.assertFalse(can_edit_form_location(self.domain, user, form), msg=msg)
