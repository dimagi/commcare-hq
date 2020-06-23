from django.test import TestCase

from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.models import Domain
from corehq.apps.locations.tests.util import delete_all_locations, make_loc
from corehq.apps.users.dbaccessors.all_commcare_users import (
    delete_all_users,
    get_all_commcare_users_by_domain,
    get_all_user_ids,
    get_all_usernames_by_domain,
    get_commcare_users_by_filters,
    get_deleted_user_by_username,
    get_existing_usernames,
    get_user_docs_by_username,
    hard_delete_deleted_users,
)
from corehq.apps.users.dbaccessors.couch_users import get_user_id_by_username
from corehq.apps.users.models import (
    CommCareUser,
    Permissions,
    UserRole,
    WebUser,
)


class AllCommCareUsersTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(AllCommCareUsersTest, cls).setUpClass()
        delete_all_users()
        hard_delete_deleted_users()
        cls.ccdomain = Domain(name='cc_user_domain')
        cls.ccdomain.save()
        cls.other_domain = Domain(name='other_domain')
        cls.other_domain.save()
        bootstrap_location_types(cls.ccdomain.name)

        UserRole.init_domain_with_presets(cls.ccdomain.name)
        cls.user_roles = UserRole.by_domain(cls.ccdomain.name)
        cls.custom_role = UserRole.get_or_create_with_permissions(
            cls.ccdomain.name,
            Permissions(
                edit_apps=True,
                edit_web_users=True,
                view_web_users=True,
                view_roles=True,
            ),
            "Custom Role"
        )
        cls.custom_role.save()

        cls.loc1 = make_loc('spain', domain=cls.ccdomain.name, type="district")
        cls.loc2 = make_loc('madagascar', domain=cls.ccdomain.name, type="district")

        cls.ccuser_1 = CommCareUser.create(
            domain=cls.ccdomain.name,
            username='ccuser_1',
            password='secret',
            created_by=None,
            created_via=None,
            email='email@example.com',
        )
        cls.ccuser_1.set_location(cls.loc1)
        cls.ccuser_1.save()
        cls.ccuser_2 = CommCareUser.create(
            domain=cls.ccdomain.name,
            username='ccuser_2',
            password='secret',
            created_by=None,
            created_via=None,
            email='email1@example.com',
        )
        cls.ccuser_2.set_role(cls.ccdomain.name, cls.custom_role.get_qualified_id())
        cls.ccuser_2.set_location(cls.loc2)
        cls.ccuser_2.save()

        cls.web_user = WebUser.create(
            domain=cls.ccdomain.name,
            username='webuser',
            password='secret',
            created_by=None,
            created_via=None,
            email='webuser@example.com',
        )
        cls.ccuser_other_domain = CommCareUser.create(
            domain=cls.other_domain.name,
            username='cc_user_other_domain',
            password='secret',
            created_by=None,
            created_via=None,
            email='email_other_domain@example.com',
        )
        cls.retired_user = CommCareUser.create(
            domain=cls.ccdomain.name,
            username='retired_user',
            password='secret',
            created_by=None,
            created_via=None,
            email='retired_user_email@example.com',
        )
        cls.retired_user.retire()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        delete_all_locations()
        cls.ccdomain.delete()
        cls.other_domain.delete()
        super(AllCommCareUsersTest, cls).tearDownClass()

    def test_get_all_commcare_users_by_domain(self):
        from corehq.util.elastic import ensure_index_deleted
        from corehq.elastic import get_es_new, send_to_elasticsearch
        from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO, USER_INDEX
        from pillowtop.es_utils import initialize_index_and_mapping

        es = get_es_new()
        ensure_index_deleted(USER_INDEX)
        initialize_index_and_mapping(es, USER_INDEX_INFO)
        send_to_elasticsearch('users', self.ccuser_1.to_json())
        send_to_elasticsearch('users', self.ccuser_2.to_json())
        es.indices.refresh(USER_INDEX)

        usernames = lambda users: [u.username for u in users]
        # if no filters are passed, should return all cc-users in the domain
        self.assertItemsEqual(
            usernames(get_commcare_users_by_filters(self.ccdomain.name, {})),
            usernames([self.ccuser_2, self.ccuser_1])
        )
        self.assertEqual(
            get_commcare_users_by_filters(self.ccdomain.name, {}, count_only=True),
            2
        )
        # can search by username
        self.assertItemsEqual(
            usernames(get_commcare_users_by_filters(self.ccdomain.name, {'search_string': 'user_1'})),
            [self.ccuser_1.username]
        )
        self.assertEqual(
            get_commcare_users_by_filters(self.ccdomain.name, {'search_string': 'user_1'}, count_only=True),
            1
        )
        # can search by role_id
        self.assertItemsEqual(
            usernames(get_commcare_users_by_filters(self.ccdomain.name, {'role_id': self.custom_role._id})),
            [self.ccuser_2.username]
        )
        self.assertEqual(
            get_commcare_users_by_filters(self.ccdomain.name, {'role_id': self.custom_role._id}, count_only=True),
            1
        )
        # can search by location
        self.assertItemsEqual(
            usernames(get_commcare_users_by_filters(self.ccdomain.name, {'location_id': self.loc1._id})),
            [self.ccuser_1.username]
        )
        self.assertEqual(
            get_commcare_users_by_filters(self.ccdomain.name, {'location_id': self.loc1._id}, count_only=True),
            1
        )

        ensure_index_deleted(USER_INDEX)

    def test_get_commcare_users_by_filters(self):
        expected_users = [self.ccuser_2, self.ccuser_1]
        expected_usernames = [user.username for user in expected_users]
        actual_usernames = [user.username for user in get_all_commcare_users_by_domain(self.ccdomain.name)]
        self.assertItemsEqual(actual_usernames, expected_usernames)

    def test_get_all_usernames_by_domain(self):
        all_cc_users = [self.ccuser_1, self.ccuser_2, self.web_user]
        expected_usernames = [user.username for user in all_cc_users]
        actual_usernames = get_all_usernames_by_domain(self.ccdomain.name)
        self.assertItemsEqual(actual_usernames, expected_usernames)

    def test_exclude_retired_users(self):
        deleted_user = CommCareUser.create(
            domain=self.ccdomain.name,
            username='deleted_user',
            password='secret',
            created_by=None,
            created_via=None,
            email='deleted_email@example.com',
        )
        deleted_user.retire()
        self.assertNotIn(
            deleted_user.username,
            [user.username for user in
             get_all_commcare_users_by_domain(self.ccdomain.name)]
        )
        deleted_user.delete()

    def test_get_user_docs_by_username(self):
        users = [self.ccuser_1, self.web_user, self.ccuser_other_domain]
        usernames = [u.username for u in users] + ['nonexistant@username.com']
        self.assertItemsEqual(
            get_user_docs_by_username(usernames),
            [u.to_json() for u in users]
        )

    def test_get_existing_usernames(self):
        users = [self.ccuser_1, self.web_user, self.ccuser_other_domain, self.retired_user]
        usernames = [u.username for u in users] + ['nonexistant@username.com']
        self.assertItemsEqual(
            get_existing_usernames(usernames),
            [u.username for u in users]
        )

    def test_get_all_ids(self):
        all_ids = get_all_user_ids()
        self.assertEqual(4, len(all_ids))
        for id in [self.ccuser_1._id, self.ccuser_2._id, self.web_user._id, self.ccuser_other_domain._id]:
            self.assertTrue(id in all_ids)

    def test_get_id_by_username(self):
        user_id = get_user_id_by_username(self.ccuser_1.username)
        self.assertEqual(user_id, self.ccuser_1._id)

    def test_get_deleted_user_by_username(self):
        self.assertEqual(self.retired_user['_id'],
                         get_deleted_user_by_username(CommCareUser, self.retired_user.username)['_id'])
        self.assertEqual(None, get_deleted_user_by_username(CommCareUser, self.ccuser_2.username))
