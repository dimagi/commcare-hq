from django.test import TestCase
from corehq.apps.groups.models import Group
from corehq.apps.users.cases import get_wrapped_owner, get_owning_users
from corehq.apps.users.models import CommCareUser
from six.moves import range

from corehq.apps.users.util import user_id_to_username
from corehq.util.test_utils import generate_cases


class CaseUtilsTestCase(TestCase):

    def setUp(self):
        self.domain = 'test'

    def test_get_wrapped_user(self):
        user = CommCareUser.create(self.domain, 'wrapped-user-test', 'password')
        user.save()
        self.addCleanup(user.delete)
        wrapped = get_wrapped_owner(user._id)
        self.assertTrue(isinstance(wrapped, CommCareUser))

    def test_get_wrapped_group(self):
        group = Group(domain=self.domain, name='wrapped-group-test')
        group.save()
        self.addCleanup(group.delete)
        wrapped = get_wrapped_owner(group._id)
        self.assertTrue(isinstance(wrapped, Group))

    def test_owned_by_user(self):
        user = CommCareUser.create(self.domain, 'owned-user-test', 'password')
        user.save()
        self.addCleanup(user.delete)
        owners = get_owning_users(user._id)
        self.assertEqual(1, len(owners))
        self.assertEqual(owners[0]._id, user._id)
        self.assertTrue(isinstance(owners[0], CommCareUser))

    def test_owned_by_group(self):
        ids = []
        for i in range(5):
            user = CommCareUser.create(self.domain, 'owned-group-test-user-%s' % i, 'password')
            user.save()
            self.addCleanup(user.delete)
            ids.append(user._id)

        group = Group(domain=self.domain, name='owned-group-test-group', users=ids)
        group.save()
        self.addCleanup(group.delete)
        owners = get_owning_users(group._id)
        self.assertEqual(5, len(owners))
        ids_back = []
        for o in owners:
            self.assertTrue(isinstance(o, CommCareUser))
            ids_back.append(o._id)
        self.assertEqual(set(ids), set(ids_back))


@generate_cases(
    (
        (1, ),
        (1.0, ),
        (None, ),
        ('', ),
        ('foobar', ),
    ),
    CaseUtilsTestCase,
)
def test_invalid_ids(self, invalid_id):
    self.assertEqual(None, get_wrapped_owner(invalid_id))
    self.assertEqual(None, user_id_to_username(invalid_id))
