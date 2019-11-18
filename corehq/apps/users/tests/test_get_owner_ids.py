from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser


class OwnerIDTestCase(TestCase):

    @staticmethod
    def _mock_user(id):
        class FakeUser(CommCareUser):

            @property
            def project(self):
                return Domain()

        user = FakeUser(_id=id, domain='test-domain')
        return user

    def test_get_owner_id_no_groups(self):
        user = self._mock_user('test-user-1')
        ids = user.get_owner_ids()
        self.assertEqual(1, len(ids))
        self.assertEqual(user._id, ids[0])

    def test_case_sharing_groups_included(self):
        user = self._mock_user('test-user-2')
        group = Group(domain='test-domain', users=['test-user-2'], case_sharing=True)
        group.save()
        ids = user.get_owner_ids()
        self.assertEqual(2, len(ids))
        self.assertEqual(user._id, ids[0])
        self.assertEqual(group._id, ids[1])

    def test_non_case_sharing_groups_not_included(self):
        user = self._mock_user('test-user-3')
        group = Group(domain='test-domain', users=['test-user-3'], case_sharing=False)
        group.save()
        ids = user.get_owner_ids()
        self.assertEqual(1, len(ids))
        self.assertEqual(user._id, ids[0])
