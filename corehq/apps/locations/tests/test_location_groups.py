from mock import patch
from corehq.apps.locations.models import LOCATION_REPORTING_PREFIX
from corehq.apps.locations.fixtures import location_fixture_generator
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.locations.tests.test_locations import LocationTestBase
from corehq import toggles
from corehq.apps.groups.exceptions import CantSaveException
from corehq.apps.users.models import CommCareUser


class LocationGroupTest(LocationTestBase):
    def setUp(self):
        super(LocationGroupTest, self).setUp()
        self.test_state = make_loc(
            'teststate',
            type='state',
            domain=self.domain.name
        )
        self.test_village = make_loc(
            'testvillage',
            type='village',
            parent=self.test_state,
            domain=self.domain.name
        )
        self.test_outlet = make_loc(
            'testoutlet',
            type='outlet',
            parent=self.test_village,
            domain=self.domain.name
        )

        toggles.MULTIPLE_LOCATIONS_PER_USER.set("domain:{}".format(self.domain.name), True)

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

        # reporting group is similar but has no ending
        self.assertEqual(
            'teststate/testvillage/testoutlet',
            self.test_outlet.sql_location.reporting_group_object().name
        )

    def test_id_assignment(self):
        # each should have the same id, but with a different prefix
        self.assertEqual(
            self.test_outlet._id,
            self.test_outlet.sql_location.case_sharing_group_object()._id
        )
        self.assertEqual(
            LOCATION_REPORTING_PREFIX + self.test_outlet._id,
            self.test_outlet.sql_location.reporting_group_object()._id
        )

    def test_group_properties(self):
        # case sharing groups should ... be case sharing
        self.assertTrue(
            self.test_outlet.sql_location.case_sharing_group_object().case_sharing
        )
        self.assertFalse(
            self.test_outlet.sql_location.case_sharing_group_object().reporting
        )

        # and reporting groups reporting
        self.assertFalse(
            self.test_outlet.sql_location.reporting_group_object().case_sharing
        )
        self.assertTrue(
            self.test_outlet.sql_location.reporting_group_object().reporting
        )

        # both should set domain properly
        self.assertEqual(
            self.domain.name,
            self.test_outlet.sql_location.reporting_group_object().domain
        )
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
            self.loc.group_id
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
        loc_type = self.loc.location_type_object
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

        self.assertDictEqual(
            {
                'commcare_location_type': self.loc.location_type,
                'commcare_location_name': self.loc.name,
                'commcare_location_foo': 'bar',
                'commcare_location_fruit': 'banana'
            },
            self.loc.sql_location.case_sharing_group_object().metadata
        )
        self.assertDictEqual(
            {
                'commcare_location_type': self.loc.location_type,
                'commcare_location_name': self.loc.name,
                'commcare_location_foo': 'bar',
                'commcare_location_fruit': 'banana'
            },
            self.loc.sql_location.reporting_group_object().metadata
        )

    @patch('corehq.apps.domain.models.Domain.uses_locations', lambda: True)
    def test_location_fixture_generator(self):
        """
        This tests the location XML fixture generator. It specifically ensures that no duplicate XML
        nodes are generated when all locations have a parent and multiple locations are enabled.
        """
        self.domain.commtrack_enabled = True
        self.domain.save()
        self.loc.delete()

        state = make_loc(
            'teststate1',
            type='state',
            domain=self.domain.name
        )
        district = make_loc(
            'testdistrict1',
            type='district',
            domain=self.domain.name,
            parent=state
        )
        block = make_loc(
            'testblock1',
            type='block',
            domain=self.domain.name,
            parent=district
        )
        village = make_loc(
            'testvillage1',
            type='village',
            domain=self.domain.name,
            parent=block
        )
        outlet1 = make_loc(
            'testoutlet1',
            type='outlet',
            domain=self.domain.name,
            parent=village
        )
        outlet2 = make_loc(
            'testoutlet2',
            type='outlet',
            domain=self.domain.name,
            parent=village
        )
        outlet3 = make_loc(
            'testoutlet3',
            type='outlet',
            domain=self.domain.name,
            parent=village
        )
        self.user.set_location(outlet2)
        self.user.add_location_delegate(outlet1)
        self.user.add_location_delegate(outlet2)
        self.user.add_location_delegate(outlet3)
        self.user.add_location_delegate(state)
        self.user.save()
        fixture = location_fixture_generator(self.user, '2.0')
        self.assertEquals(len(fixture[0].findall('.//state')), 1)
        self.assertEquals(len(fixture[0].findall('.//outlet')), 3)
