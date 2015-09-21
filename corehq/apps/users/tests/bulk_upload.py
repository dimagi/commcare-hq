from collections import defaultdict
from contextlib import nested
from datetime import datetime
from django.test import SimpleTestCase, TestCase
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


def apply_patches(fn):
    def inner(self):
        with nested(*self.patches):
            fn(self)
    return inner


def group_mock():
    groups_by_id = {}

    class GroupMock(Group):
        @classmethod
        def by_user(cls, user_or_user_id, wrap=True, include_names=False):
            assert not include_names
            assert wrap
            try:
                user_id = user_or_user_id.user_id
            except AttributeError:
                user_id = user_or_user_id
            return [group for group in groups_by_id.values()
                    if user_id in group.users]

        def save(self, *args, **kwargs):
            self.last_modified = datetime.utcnow()
            groups_by_id[self._id] = self

        def save_docs(cls, docs, use_uuids=True, all_or_nothing=False):
            utcnow = datetime.utcnow()
            for doc in docs:
                if not isinstance(doc, Group):
                    doc = Group.wrap(doc)
                doc.last_modified = utcnow
                groups_by_id[doc._id] = doc

        bulk_save = save_docs

    return GroupMock


def commcare_user_mock():
    users_by_username = {}

    class CommCareUserMock(CommCareUser):
        def save(self):
            users_by_username[self.username] = self

        @classmethod
        def get_by_username(cls, username, strict=True):
            return users_by_username[username]

        @classmethod
        def get_by_user_id(cls, userID, domain=None):
            return None

        @classmethod
        def create(cls, domain, username, password,
                   # the following are ignored in this mock
                   email=None, uuid='', date='', phone_number=None,
                   commit=True, **kwargs):
            return cls(
                domain=domain, username=username, password=password)
    return CommCareUserMock


class TestUserBulkUpload(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='mydomain')
        cls.domain.save()

    def setUp(self):
        def domain_has_privilege(domain, privilege):
            return False

        @classmethod
        def UserFieldsView__get_validator(cls, domain):
            return lambda dct: ''

        @classmethod
        def Domain__get_by_name(cls, domain):
            return self.domain

        self.patches = [
            patch('corehq.apps.accounting.utils.domain_has_privilege', domain_has_privilege),
            patch.object(UserFieldsView, 'get_validator', UserFieldsView__get_validator),
            patch.object(GroupMemoizer, 'load_all', lambda _self: None),
            patch.object(GroupMemoizer, 'save_all', lambda _self: None),
            patch('corehq.apps.groups.models.Group', group_mock()),
            patch.object(Domain, 'get_by_name', Domain__get_by_name),
            patch('corehq.apps.users.models.CommCareUser', commcare_user_mock()),
        ]

    @apply_patches
    def test_upload_with_user_id(self):
        user_specs = [{
            u'username': u'hello',
            u'user_id': u'should not update',
            u'name': u'Another One',
            u'language': None,
            u'is_active': u'True',
            u'phone-number': u'23424123',
            u'password': 123,
            u'email': None
        }]
        messages = bulk_upload_async(
            self.domain.name,
            user_specs,
            list([]),
            list([])
        )['messages']['rows']
        message = messages[0]['flag']
        user = CommCareUser.get_by_username('{}@{}.commcarehq.org'.format(
            user_specs[0]['username'],
            self.domain.name))
        self.assertNotEqual(user_specs[0]['user_id'], user._id)
        self.assertEqual(user_specs[0]['phone-number'], user.phone_number)
        self.assertEqual(user_specs[0]['name'], user.name)
        self.assertEqual(len(messages), 1)
        self.assertEqual(message, 'created')

    @apply_patches
    def test_upload_with_duplicate_group(self):
        group_1 = {
            u'case-sharing': False,
            u'reporting': True,
            u'name': u'Team Inferno'
        }
        group_2 = {
            u'case-sharing': False,
            u'reporting': False,
            u'name': u'Team Inferno'
        }
        group_specs = [group_1, group_2]
        messages = bulk_upload_async(self.domain.name, [], group_specs, [])
        groups = Group.by_name(domain=self.domain.name, name=u'Team Inferno',
                               one=False).all()
        self.assertEqual(len(groups), 1)
        [group] = groups
        self.assertEqual(group.name, group_1['name'])
        # assert the one that got processed was the first one, not the second
        self.assertEqual(group.reporting, group_1['reporting'])
        self.assertNotEqual(group.reporting, group_2['reporting'])
