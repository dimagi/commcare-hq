from contextlib import nested
from django.test import SimpleTestCase
from corehq.apps.commtrack.tests.util import CommTrackTest, make_loc
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.users.bulkupload import UserLocMapping, SiteCodeToSupplyPointCache, \
    GroupMemoizer
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from mock import patch
from corehq.apps.users.views.mobile import UserFieldsView
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


class TestUserBulkUpload(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='mydomain')
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

    def setUp(self):
        def domain_has_privilege(domain, privilege):
            return False

        @classmethod
        def UserFieldsView__get_validator(cls, domain):
            return lambda dct: ''

        def CommCareUser__save(_self):
            self.users_by_username[_self.username] = _self

        @classmethod
        def CommCareUser__get_by_username(_self, username):
            return self.users_by_username[username]

        @classmethod
        def CommCareUser__get_by_user_id(cls, user_id, domain):
            return None

        @classmethod
        def CommCareUser__create(cls, domain, username, password, commit):
            return CommCareUser(
                domain=domain, username=username, password=password)

        @classmethod
        def Domain__get_by_name(cls, domain):
            return self.domain

        @classmethod
        def Group__by_user(cls, domain, wrap):
            return []

        self.patches = [
            patch('corehq.apps.accounting.utils.domain_has_privilege', domain_has_privilege),
            patch.object(UserFieldsView, 'get_validator', UserFieldsView__get_validator),
            patch.object(GroupMemoizer, 'load_all', lambda _self: None),
            patch.object(GroupMemoizer, 'save_all', lambda _self: None),
            patch.object(Group, 'by_user', Group__by_user),
            patch.object(Domain, 'get_by_name', Domain__get_by_name),
            patch.object(CommCareUser, 'get_by_user_id', CommCareUser__get_by_user_id),
            patch.object(CommCareUser, 'create', CommCareUser__create),
            patch.object(CommCareUser, 'save', CommCareUser__save),
            patch.object(CommCareUser, 'get_by_username', CommCareUser__get_by_username),
        ]

        self.users_by_username = {}

    def test_upload_with_user_id(self):
        with nested(*self.patches):
            self._test_upload_with_user_id()

    def _test_upload_with_user_id(self):
        messages = bulk_upload_async(
            self.domain.name,
            list(self.user_specs),
            list([]),
            list([])
        )['messages']['rows']
        message = messages[0]['flag']
        user = CommCareUser.get_by_username('{}@{}.commcarehq.org'.format(
            self.user_specs[0]['username'],
            self.domain.name))
        self.assertNotEqual(self.user_specs[0]['user_id'], user._id)
        self.assertEqual(self.user_specs[0]['phone-number'], user.phone_number)
        self.assertEqual(self.user_specs[0]['name'], user.name)
        self.assertEqual(len(messages), 1)
        self.assertEqual(message, 'created')
