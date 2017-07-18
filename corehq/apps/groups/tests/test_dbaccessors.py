from django.test import TestCase
from corehq.apps.groups.dbaccessors import get_groups_by_user
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser


class DbaccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'groups-dbaccessors-test'

        cls.user_1 = CommCareUser.create(cls.domain, 'user1@example.com', '***')
        cls.user_2 = CommCareUser.create(cls.domain, 'user2@example.com', '***')

        cls.group_1 = Group(domain=cls.domain)
        cls.group_1.add_user(cls.user_1, save=False)
        cls.group_1.add_user(cls.user_2, save=False)
        cls.group_1.save()

        cls.group_2 = Group(domain=cls.domain)
        cls.group_2.add_user(cls.user_2, save=False)
        cls.group_2.save()

    @classmethod
    def tearDownClass(cls):
        cls.user_1.delete()
        cls.user_2.delete()
        cls.group_1.delete()
        cls.group_2.delete()

    def test_get_groups_by_user(self):
        self.assertEqual(
            get_groups_by_user(self.domain, [self.user_1.user_id]),
            {
                self.user_1.user_id: {self.group_1._id, }
            }
        )
        self.assertEqual(
            get_groups_by_user(self.domain, [self.user_2.user_id]),
            {
                self.user_2.user_id: {self.group_1._id, self.group_2._id}
            }
        )
        self.assertEqual(
            get_groups_by_user(self.domain, [self.user_1.user_id, self.user_2.user_id]),
            {
                self.user_2.user_id: {self.group_1._id, self.group_2._id},
                self.user_1.user_id: {self.group_1._id},
            }
        )
        self.assertEqual(
            get_groups_by_user(self.domain, ['no-user']),
            {}
        )
        with self.assertRaises(AssertionError):
            get_groups_by_user('no-domain', [self.user_1.user_id]),
