from django.test import TestCase

from unittest.mock import patch

from casexml.apps.phone.tests.utils import call_fixture_generator

from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.exceptions import CantSaveException
from corehq.apps.users.models import CommCareUser
from corehq.util.test_utils import flag_enabled

from ..fixtures import location_fixture_generator
from .util import make_loc


class LocationGroupBase(TestCase):

    @classmethod
    def setUpClass(cls, set_location=True):
        super().setUpClass()
        cls.domain = create_domain('locations-test')
        cls.domain.convert_to_commtrack()
        bootstrap_location_types(cls.domain.name)
        cls.loc = make_loc('loc', type='outlet', domain=cls.domain.name)

        cls.user = CommCareUser.create(
            cls.domain.name,
            'username',
            'password',
            created_by=None,
            created_via=None,
            first_name='Bob',
            last_name='Builder',
        )
        if set_location:
            cls.user.set_location(cls.loc)

        cls.test_state = make_loc(
            'teststate',
            type='state',
            domain=cls.domain.name
        )
        cls.test_village = make_loc(
            'testvillage',
            type='village',
            parent=cls.test_state,
            domain=cls.domain.name
        )
        cls.test_outlet = make_loc(
            'testoutlet',
            type='outlet',
            parent=cls.test_village,
            domain=cls.domain.name
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super().tearDownClass()


class LocationGroupTest(LocationGroupBase):

    def test_group_name(self):
        # just location name for top level
        self.assertEqual(
            'teststate-Cases',
            self.test_state.sql_location.case_sharing_group_object().name
        )

        # locations combined by forward slashes otherwise
        self.assertEqual(
            'teststate/testvillage/testoutlet-Cases',
            self.test_outlet.sql_location.case_sharing_group_object().name
        )

    def test_id_assignment(self):
        # each should have the same id, but with a different prefix
        self.assertEqual(
            self.test_outlet._id,
            self.test_outlet.sql_location.case_sharing_group_object()._id
        )

    def test_group_properties(self):
        # case sharing groups should ... be case sharing
        self.assertTrue(
            self.test_outlet.sql_location.case_sharing_group_object().case_sharing
        )
        self.assertFalse(
            self.test_outlet.sql_location.case_sharing_group_object().reporting
        )

        # and should set domain properly
        self.assertEqual(
            self.domain.name,
            self.test_outlet.sql_location.case_sharing_group_object().domain
        )

    def test_accessory_methods(self):
        # we need to expose group id without building the group sometimes
        # so lets make sure those match up
        expected_id = self.loc.sql_location.case_sharing_group_object()._id
        self.assertEqual(
            expected_id,
            self.loc.location_id
        )

    def test_not_real_groups(self):
        # accessing a group object should not cause it to save
        # in the DB
        group_obj = self.test_outlet.sql_location.case_sharing_group_object()
        self.assertNotEqual(group_obj.doc_type, 'Group')

    def test_cant_save_wont_save(self):
        group_obj = self.test_outlet.sql_location.case_sharing_group_object()
        with self.assertRaises(CantSaveException):
            group_obj.save()

    def test_get_owner_ids(self):
        loc_type = self.loc.location_type
        self.assertFalse(loc_type.shares_cases)
        owner_ids = self.user.get_owner_ids()
        self.assertEqual(1, len(owner_ids))
        self.assertEqual(self.user._id, owner_ids[0])

        # change it so case sharing is enabled and make sure it is now included
        loc_type.shares_cases = True
        loc_type.save()
        # we have to re-create the user object because various things are cached
        user = CommCareUser.wrap(self.user.to_json())
        owner_ids = user.get_owner_ids()
        self.assertEqual(2, len(owner_ids))
        self.assertEqual(self.loc.location_id, owner_ids[1])

        # set it back to false in case other tests needed that
        loc_type.shares_cases = False
        loc_type.save()

    def test_custom_data(self):
        # need to put the location data on the
        # group with a special prefix
        self.loc.metadata = {
            'foo': 'bar',
            'fruit': 'banana'
        }
        self.loc.save()

        def cleanup():
            self.loc.metadata = {}
            self.loc.save()
        self.addCleanup(cleanup)

        self.assertDictEqual(
            {
                'commcare_location_type': self.loc.location_type_name,
                'commcare_location_name': self.loc.name,
                'commcare_location_foo': 'bar',
                'commcare_location_fruit': 'banana'
            },
            self.loc.sql_location.case_sharing_group_object().metadata
        )


@flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
class UnsetLocationGroupTest(LocationGroupBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass(set_location=False)

    @patch('corehq.apps.domain.models.Domain.uses_locations', lambda: True)
    def test_location_fixture_generator_no_user_location(self):
        """
        Ensures that a user without a location will still receive an empty fixture
        """
        assert self.user.location is None
        restore_user = self.user.to_ota_restore_user(self.domain.name)
        fixture = call_fixture_generator(location_fixture_generator, restore_user)
        self.assertEqual(len(fixture), 1)
        self.assertEqual(len(fixture[0].findall('.//state')), 0)

    def test_location_fixture_generator_domain_no_locations(self):
        """
        Ensures that a domain that doesn't use locations doesn't send an empty
        location fixture
        """
        assert self.user.location is None
        restore_user = self.user.to_ota_restore_user(self.domain.name)
        fixture = call_fixture_generator(location_fixture_generator, restore_user)
        self.assertEqual(len(fixture), 0)
