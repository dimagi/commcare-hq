from datetime import datetime

from django.test import TestCase

from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.models import Domain
from corehq.apps.es.tests.utils import es_test, populate_user_index
from corehq.apps.locations.tests.util import delete_all_locations, make_loc
from corehq.apps.users.dbaccessors import (
    count_invitations_by_filters,
    count_mobile_users_by_filters,
    count_web_users_by_filters,
    delete_all_users,
    get_all_commcare_users_by_domain,
    get_all_user_ids,
    get_all_usernames_by_domain,
    get_all_web_users_by_domain,
    get_deleted_user_by_username,
    get_existing_usernames,
    get_invitations_by_filters,
    get_user_docs_by_username,
    get_user_id_by_username,
    get_mobile_users_by_filters,
    get_web_users_by_filters,
    hard_delete_deleted_users,
)
from corehq.apps.users.models import (
    CommCareUser,
    Invitation,
    Permissions,
    UserRole,
    WebUser,
)
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.util.elastic import ensure_index_deleted
from corehq.apps.users.role_utils import init_domain_with_presets


@es_test
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

        init_domain_with_presets(cls.ccdomain.name)
        cls.user_roles = UserRole.by_domain(cls.ccdomain.name)
        cls.custom_role = UserRole.create(cls.ccdomain.name, "Custom Role")

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
        cls.retired_user.retire(cls.ccdomain.name, deleted_by=None)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        delete_all_locations()
        cls.ccdomain.delete()
        cls.other_domain.delete()
        super(AllCommCareUsersTest, cls).tearDownClass()

    def test_get_users_by_filters(self):
        populate_user_index([
            self.ccuser_1.to_json(),
            self.ccuser_2.to_json(),
            self.web_user.to_json(),
        ])

        def usernames(users):
            return [u.username for u in users]

        # if no filters are passed, should return all users of given type in the domain
        self.assertItemsEqual(
            usernames(get_mobile_users_by_filters(self.ccdomain.name, {})),
            usernames([self.ccuser_2, self.ccuser_1])
        )
        self.assertEqual(count_mobile_users_by_filters(self.ccdomain.name, {}), 2)
        self.assertItemsEqual(
            usernames(get_web_users_by_filters(self.ccdomain.name, {})),
            usernames([self.web_user])
        )
        self.assertEqual(count_web_users_by_filters(self.ccdomain.name, {}), 1)

        # can search by username
        filters = {'search_string': 'user_1'}
        self.assertItemsEqual(
            usernames(get_mobile_users_by_filters(self.ccdomain.name, filters)),
            [self.ccuser_1.username]
        )
        self.assertEqual(count_mobile_users_by_filters(self.ccdomain.name, filters), 1)

        filters = {'search_string': 'webuser'}
        self.assertItemsEqual(
            usernames(get_web_users_by_filters(self.ccdomain.name, filters)),
            [self.web_user.username]
        )
        self.assertEqual(count_web_users_by_filters(self.ccdomain.name, filters), 1)

        filters = {'search_string': 'notwebuser'}
        self.assertItemsEqual(usernames(get_mobile_users_by_filters(self.ccdomain.name, filters)), [])
        self.assertEqual(count_mobile_users_by_filters(self.ccdomain.name, filters), 0)

        # can search by role_id
        filters = {'role_id': self.custom_role._id}
        self.assertItemsEqual(
            usernames(get_mobile_users_by_filters(self.ccdomain.name, filters)),
            [self.ccuser_2.username]
        )
        self.assertEqual(count_mobile_users_by_filters(self.ccdomain.name, filters), 1)

        # can search by location
        filters = {'location_id': self.loc1._id}
        self.assertItemsEqual(
            usernames(get_mobile_users_by_filters(self.ccdomain.name, filters)),
            [self.ccuser_1.username]
        )
        filters = {'location_id': self.loc1._id}
        self.assertEqual(count_mobile_users_by_filters(self.ccdomain.name, filters), 1)

        ensure_index_deleted(USER_INDEX)

    def test_get_invitations_by_filters(self):
        invitations = [
            Invitation(domain=self.ccdomain.name, email='wolfgang@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow(), role=self.custom_role.get_qualified_id()),
            Invitation(domain=self.ccdomain.name, email='sergei_p@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow()),
            Invitation(domain=self.ccdomain.name, email='sergei_r@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow()),
            Invitation(domain=self.ccdomain.name, email='ludwig@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow(), is_accepted=True),
        ]
        for inv in invitations:
            inv.save()

        self._assert_invitations({}, ["sergei_p@email.com", "sergei_r@email.com", "wolfgang@email.com"])
        self._assert_invitations({"search_string": "Sergei"}, ["sergei_p@email.com", "sergei_r@email.com"])
        self._assert_invitations({"role_id": self.custom_role._id}, ["wolfgang@email.com"])

        for inv in invitations:
            inv.delete()

    def _assert_invitations(self, filters, expected_emails):
        self.assertEqual(
            {i.email for i in get_invitations_by_filters(self.ccdomain.name, filters)},
            set(expected_emails)
        )
        self.assertEqual(
            count_invitations_by_filters(self.ccdomain.name, filters),
            len(expected_emails)
        )

    def test_get_all_commcare_users_by_domain(self):
        expected_users = [self.ccuser_2, self.ccuser_1]
        expected_usernames = [user.username for user in expected_users]
        actual_usernames = [user.username for user in get_all_commcare_users_by_domain(self.ccdomain.name)]
        self.assertItemsEqual(actual_usernames, expected_usernames)

    def test_get_all_web_users_by_domain(self):
        expected_users = [self.web_user]
        expected_usernames = [user.username for user in expected_users]
        actual_usernames = [user.username for user in get_all_web_users_by_domain(self.ccdomain.name)]
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
        deleted_user.retire(self.ccdomain.name, deleted_by=None)
        self.assertNotIn(
            deleted_user.username,
            [user.username for user in
             get_all_commcare_users_by_domain(self.ccdomain.name)]
        )
        deleted_user.delete(self.ccdomain.name, deleted_by=None)

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
