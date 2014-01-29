from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.commtrack.helpers import make_supply_point
from casexml.apps.case.tests.util import check_user_has_case
from casexml.apps.case.xml import V2
from casexml.apps.case.mock import CaseBlock
from mock import patch


class LocationsTest(CommTrackTest):

    def check_supply_point(self, user, sp, should_have=True):
        caseblock = CaseBlock(
            create=False,
            case_id=sp,
            version=V2,
        ).as_xml()
        check_user_has_case(
            self,
            user.to_casexml_user(),
            caseblock,
            line_by_line=False,
            should_have=should_have,
            version=V2
        )

    def test_location_assignment(self):
        user = self.reporters['fixed']

        self.assertEqual(len(user.locations), 1)
        self.assertEqual(user.locations[0].name, 'loc1')
        self.check_supply_point(user, self.sp._id)

    def test_commtrack_user_has_multiple_locations(self):
        user = self.reporters['fixed']

        loc = make_loc('secondloc')
        sp = make_supply_point(self.domain.name, loc)
        user.add_location(loc)

        self.check_supply_point(user, sp._id)
        self.assertTrue(len(user.locations), 2)
        self.assertEqual(user.locations[1].name, 'secondloc')

    def test_locations_can_be_removed(self):
        user = self.reporters['fixed']

        # can't test with the original since the user already owns it
        loc = make_loc('secondloc')
        sp = make_supply_point(self.domain.name, loc)
        user.add_location(loc)

        self.check_supply_point(user, sp._id)

        user.remove_location(loc)

        self.check_supply_point(user, sp._id, False)
        self.assertEqual(len(user.locations), 1)

    def test_location_removal_only_submits_if_it_existed(self):
        user = self.reporters['fixed']

        # can't test with the original since the user already owns it
        loc = make_loc('secondloc')
        make_supply_point(self.domain.name, loc)

        with patch('corehq.apps.commtrack.models.CommTrackUser.submit_location_block') as submit_blocks:
            user.remove_location(loc)
            self.assertEqual(submit_blocks.call_count, 0)


    def test_can_clear_locations(self):
        user = self.reporters['fixed']
        user.clear_locations()

        self.assertEqual(len(user.locations), 0)

    def test_can_set_locations(self):
        user = self.reporters['fixed']

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
        user = self.reporters['fixed']

        loc1 = make_loc('secondloc')
        make_supply_point(self.domain.name, loc1)

        with patch('corehq.apps.commtrack.models.CommTrackUser.submit_location_block') as submit_blocks:
            user.set_locations([loc1])
            self.assertEqual(submit_blocks.call_count, 1)

    def test_setting_existing_list_does_not_submit(self):
        user = self.reporters['fixed']

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
