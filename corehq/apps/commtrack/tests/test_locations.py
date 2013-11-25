from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.commtrack.helpers import make_supply_point
from casexml.apps.case.tests.util import check_user_has_case
from casexml.apps.case.xml import V2
from casexml.apps.case.mock import CaseBlock


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
        sp = make_supply_point(self.domain, loc)
        user.add_location(loc)

        self.check_supply_point(user, sp._id)
        self.assertTrue(len(user.locations), 2)
        self.assertEqual(user.locations[1].name, 'secondloc')

    def test_locations_can_be_removed(self):
        user = self.reporters['fixed']

        # can't test with the original since the user already owns it
        loc = make_loc('secondloc')
        sp = make_supply_point(self.domain, loc)
        user.add_location(loc)

        self.check_supply_point(user, sp._id)

        user.remove_location(loc)

        self.check_supply_point(user, sp._id, False)
        self.assertTrue(len(user.locations), 0)
