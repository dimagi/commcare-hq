from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.users.bulkupload import UserLocMapping, LocationCache
from corehq.apps.users.models import CommCareUser
from corehq.apps.commtrack.models import CommTrackUser
from mock import patch


class UserLocMapTest(CommTrackTest):
    def setUp(self):
        super(UserLocMapTest, self).setUp()

        self.user = CommCareUser.create(
            self.domain.name,
            'commcareuser',
            'password',
            phone_numbers=['123123'],
            user_data={},
            first_name='test',
            last_name='user'
        )
        self.ct_user = CommTrackUser.wrap(self.user.to_json())

        self.loc = make_loc('secondloc')
        self.sp = make_supply_point(self.domain, self.loc)
        self.cache = LocationCache()
        self.mapping = UserLocMapping(self.user.username, self.user.domain, self.cache)

    def test_adding_a_location(self):
        self.mapping.to_add.add(self.loc.site_code)

        self.assertEqual(len(self.ct_user.locations), 0)
        self.mapping.save()
        self.assertEqual(len(self.ct_user.locations), 1)

    def test_removing_a_location(self):
        self.mapping.to_remove.add(self.loc.site_code)

        # first make sure there is one to remove
        self.ct_user.add_location(self.loc)
        self.assertEqual(len(self.ct_user.locations), 1)
        self.mapping.save()
        self.assertEqual(len(self.ct_user.locations), 0)

    def test_should_not_add_what_is_already_there(self):
        self.mapping.to_add.add(self.loc.site_code)

        self.ct_user.add_location(self.loc)

        with patch('corehq.apps.hqcase.utils.submit_case_blocks') as submit_blocks:
            self.mapping.save()
            assert not submit_blocks.called, 'Should not submit case block if user already has location'

    def test_should_not_delete_what_is_not_there(self):
        self.mapping.to_remove.add(self.loc.site_code)

        with patch('corehq.apps.hqcase.utils.submit_case_blocks') as submit_blocks:
            self.mapping.save()
            assert not submit_blocks.called, 'Should not submit case block if user already has location'

    def test_location_lookup_caching(self):
        user2 = CommCareUser.create(
            self.domain.name,
            'commcareuser2',
            'password',
            phone_numbers=['123123'],
            user_data={},
            first_name='test',
            last_name='user'
        )
        mapping2 = UserLocMapping(user2.username, user2.domain, self.cache)

        self.mapping.to_add.add(self.loc.site_code)
        mapping2.to_add.add(self.loc.site_code)

        with patch('corehq.apps.commtrack.util.SupplyPointCase.get_by_location') as get_supply_point:
            self.mapping.save()
            mapping2.save()
            self.assertEqual(get_supply_point.call_count, 1)
