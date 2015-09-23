from django.test import TestCase
from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.users.bulkupload import UserLocMapping, SiteCodeToSupplyPointCache
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain
from mock import patch
from corehq.toggles import MULTIPLE_LOCATIONS_PER_USER, NAMESPACE_DOMAIN


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

        MULTIPLE_LOCATIONS_PER_USER.set(self.user.domain, True, NAMESPACE_DOMAIN)

        self.loc = make_loc('secondloc')
        self.sp = make_supply_point(self.domain.name, self.loc)
        self.cache = SiteCodeToSupplyPointCache(self.domain.name)
        self.mapping = UserLocMapping(self.user.username, self.user.domain, self.cache)

    def test_adding_a_location(self):
        self.mapping.to_add.add(self.loc.site_code)

        self.assertEqual(len(self.user.locations), 0)
        self.mapping.save()
        self.assertEqual(len(self.user.locations), 1)

    def test_removing_a_location(self):
        # first make sure there is one to remove
        self.user.add_location_delegate(self.loc)
        self.assertEqual(len(self.user.locations), 1)

        self.mapping.to_remove.add(self.loc.site_code)
        ret = self.mapping.save()
        self.assertEqual(len(self.user.locations), 0)

    def test_should_not_add_what_is_already_there(self):
        self.mapping.to_add.add(self.loc.site_code)

        self.user.add_location_delegate(self.loc)

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


class TestUserBulkUpload(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='mydomain')
        cls.domain.save()
        cls.user_specs = [{
            u'username': u'hello',
            u'user_id': u'should not update',
            u'name': u'Another One',
            u'language': None,
            u'is_active': u'True',
            u'phone-number': u'23424123',
            u'password': 123,
            u'email': None
        }]

    def test_upload_with_user_id(self):
        bulk_upload_async(
            self.domain.name,
            list(self.user_specs),
            list([]),
            list([])
        )

        user = CommCareUser.get_by_username('{}@{}.commcarehq.org'.format(
            self.user_specs[0]['username'],
            self.domain.name))
        self.assertNotEqual(self.user_specs[0]['user_id'], user._id)
        self.assertEqual(self.user_specs[0]['phone-number'], user.phone_number)
        self.assertEqual(self.user_specs[0]['name'], user.name)
