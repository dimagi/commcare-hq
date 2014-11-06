from corehq.apps.users.models import CommCareUser
from corehq.apps.locations.models import Location, SQLLocation
from casexml.apps.case.tests.util import check_user_has_case
from casexml.apps.case.xml import V2
from casexml.apps.case.mock import CaseBlock
from dimagi.utils.parsing import json_format_datetime
from mock import patch
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc, FIXED_USER
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase


class LocationsTest(CommTrackTest):
    user_definitions = [FIXED_USER]

    def setUp(self):
        super(LocationsTest, self).setUp()
        self.user = self.users[0]

    def check_supply_point(self, user, sp, should_have=True):
        caseblock = CaseBlock(
            create=False,
            case_id=sp,
            version=V2,
        ).as_xml(format_datetime=json_format_datetime)
        check_user_has_case(
            self,
            user.to_casexml_user(),
            caseblock,
            line_by_line=False,
            should_have=should_have,
            version=V2
        )

    def test_location_assignment(self):
        user = self.user

        self.assertEqual(len(user.locations), 1)
        self.assertEqual(user.locations[0].name, 'loc1')
        self.check_supply_point(user, self.sp._id)

    def test_commtrack_user_has_multiple_locations(self):
        user = self.user

        loc = make_loc('secondloc')
        sp = make_supply_point(self.domain.name, loc)
        user.add_location(loc)

        self.check_supply_point(user, sp._id)
        self.assertTrue(len(user.locations), 2)
        self.assertEqual(user.locations[1].name, 'secondloc')

    def test_locations_can_be_removed(self):
        user = self.user

        # can't test with the original since the user already owns it
        loc = make_loc('secondloc')
        sp = make_supply_point(self.domain.name, loc)
        user.add_location(loc)

        self.check_supply_point(user, sp._id)

        user.remove_location(loc)

        self.check_supply_point(user, sp._id, False)
        self.assertEqual(len(user.locations), 1)

    def test_location_removal_only_submits_if_it_existed(self):
        user = self.user

        # can't test with the original since the user already owns it
        loc = make_loc('secondloc')
        make_supply_point(self.domain.name, loc)

        with patch('corehq.apps.commtrack.models.CommTrackUser.submit_location_block') as submit_blocks:
            user.remove_location(loc)
            self.assertEqual(submit_blocks.call_count, 0)


    def test_can_clear_locations(self):
        user = self.user
        user.clear_locations()

        self.assertEqual(len(user.locations), 0)

    def test_can_set_locations(self):
        user = self.user

        loc1 = make_loc('secondloc')
        sp1 = make_supply_point(self.domain.name, loc1)

        loc2 = make_loc('thirdloc')
        sp2 = make_supply_point(self.domain.name, loc2)

        user.set_locations([loc1, loc2])

        # should only have the two new cases
        self.assertEqual(len(user.locations), 2)

        # and will have access to these two
        self.check_supply_point(user, sp1._id)
        self.check_supply_point(user, sp2._id)

    def test_setting_new_list_causes_submit(self):
        """
        this test mostly exists to make sure the one
        testing no submits doesn't silently stop actually working
        """
        user = self.user

        loc1 = make_loc('secondloc')
        make_supply_point(self.domain.name, loc1)

        with patch('corehq.apps.commtrack.models.CommTrackUser.submit_location_block') as submit_blocks:
            user.set_locations([loc1])
            self.assertEqual(submit_blocks.call_count, 1)

    def test_setting_existing_list_does_not_submit(self):
        user = self.user

        user.clear_locations()

        loc1 = make_loc('secondloc')
        make_supply_point(self.domain.name, loc1)

        loc2 = make_loc('thirdloc')
        make_supply_point(self.domain.name, loc2)

        user.add_location(loc1)
        user.add_location(loc2)

        with patch('corehq.apps.commtrack.models.CommTrackUser.submit_location_block') as submit_blocks:
            user.set_locations([loc1, loc2])
            self.assertEqual(submit_blocks.call_count, 0)

    def test_location_migration(self):
        user = CommCareUser.create(
            self.domain.name,
            'commcareuser',
            'password',
            phone_numbers=['123123'],
            user_data={},
            first_name='test',
            last_name='user'
        )

        loc = make_loc('someloc')
        make_supply_point(self.domain.name, loc)

        user.commtrack_location = loc._id
        ct_user = CommTrackUser.wrap(user.to_json())

        self.assertEqual(1, len(ct_user.locations))
        self.assertEqual('someloc', ct_user.locations[0].name)
        self.assertFalse(hasattr(ct_user, 'commtrack_location'))

    def test_sync(self):
        test_state = make_loc(
            'teststate',
            type='state',
            parent=self.user.locations[0]
        )
        test_village = make_loc(
            'testvillage',
            type='village',
            parent=test_state
        )

        try:
            sql_village = SQLLocation.objects.get(
                name='testvillage',
                domain=self.domain.name,
            )

            self.assertEqual(sql_village.name, test_village.name)
            self.assertEqual(sql_village.domain, test_village.domain)
        except SQLLocation.DoesNotExist:
            self.fail("Synced SQL object does not exist")

    def test_archive(self):
        test_state = make_loc(
            'teststate',
            type='state',
            parent=self.user.locations[0]
        )
        test_state.save()

        original_count = len(list(Location.by_domain(self.domain.name)))

        loc = self.user.locations[0]
        loc.archive()

        # it should also archive children
        self.assertEqual(
            len(list(Location.by_domain(self.domain.name))),
            original_count - 2
        )
        self.assertEqual(
            len(Location.root_locations(self.domain.name)),
            0
        )

        loc.unarchive()

        # and unarchive children
        self.assertEqual(
            len(list(Location.by_domain(self.domain.name))),
            original_count
        )
        self.assertEqual(
            len(Location.root_locations(self.domain.name)),
            1
        )

    def test_archive_flips_sp_cases(self):
        loc = make_loc('someloc')
        sp = make_supply_point(self.domain.name, loc)

        self.assertFalse(sp.closed)
        loc.archive()
        sp = SupplyPointCase.get(sp._id)
        self.assertTrue(sp.closed)

        loc.unarchive()
        sp = SupplyPointCase.get(sp._id)
        self.assertFalse(sp.closed)

    def test_location_queries(self):
        test_state1 = make_loc(
            'teststate1',
            type='state',
            parent=self.user.locations[0]
        )
        test_state2 = make_loc(
            'teststate2',
            type='state',
            parent=self.user.locations[0]
        )
        test_village1 = make_loc(
            'testvillage1',
            type='village',
            parent=test_state1
        )
        test_village1.site_code = 'tv1'
        test_village1.save()
        test_village2 = make_loc(
            'testvillage2',
            type='village',
            parent=test_state2
        )

        def compare(list1, list2):
            self.assertEqual(
                set([l._id for l in list1]),
                set([l._id for l in list2])
            )

        # descendants
        compare(
            [test_state1, test_state2, test_village1, test_village2],
            self.user.locations[0].descendants
        )

        # children
        compare(
            [test_state1, test_state2],
            self.user.locations[0].children
        )

        # siblings
        compare(
            [test_state2],
            test_state1.siblings()
        )

        # parent and parent_id
        self.assertEqual(
            self.user.locations[0]._id,
            test_state1.parent_id
        )
        self.assertEqual(
            self.user.locations[0]._id,
            test_state1.parent._id
        )


        # is_root
        self.assertTrue(self.user.locations[0].is_root)
        self.assertFalse(test_state1.is_root)

        # Location.root_locations
        compare(
            [self.user.locations[0]],
            Location.root_locations(self.domain.name)
        )

        # Location.filter_by_type
        compare(
            [test_village1, test_village2],
            Location.filter_by_type(self.domain.name, 'village')
        )
        compare(
            [test_village1],
            Location.filter_by_type(self.domain.name, 'village', test_state1)
        )

        # Location.filter_by_type_count
        self.assertEqual(
            2,
            Location.filter_by_type_count(self.domain.name, 'village')
        )
        self.assertEqual(
            1,
            Location.filter_by_type_count(self.domain.name, 'village', test_state1)
        )

        # Location.get_in_domain
        test_village2.domain = 'rejected'
        test_village2.save()
        self.assertEqual(
            Location.get_in_domain(self.domain.name, test_village1._id)._id,
            test_village1._id
        )
        self.assertIsNone(
            Location.get_in_domain(self.domain.name, test_village2._id),
        )
        self.assertIsNone(
            Location.get_in_domain(self.domain.name, 'not-a-real-id'),
        )

        # Location.all_locations
        compare(
            [self.user.locations[0], test_state1, test_state2, test_village1],
            Location.all_locations(self.domain.name)
        )

        # Location.by_site_code
        self.assertEqual(
            test_village1._id,
            Location.by_site_code(self.domain.name, 'tv1')._id
        )
        self.assertIsNone(
            None,
            Location.by_site_code(self.domain.name, 'notreal')
        )

        # Location.by_domain
        compare(
            [self.user.locations[0], test_state1, test_state2, test_village1],
            Location.by_domain(self.domain.name)
        )
