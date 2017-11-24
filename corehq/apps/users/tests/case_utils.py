from __future__ import absolute_import
from builtins import range
from django.test import TestCase
from corehq.apps.groups.models import Group
from corehq.apps.users.cases import get_wrapped_owner, get_owning_users
from corehq.apps.users.models import CommCareUser


class CaseUtilsTestCase(TestCase):

    def setUp(self):
        self.domain = 'test'

    def test_get_wrapped_user(self):
        user = CommCareUser.create(self.domain, 'wrapped-user-test', 'password')
        user.save()
        wrapped = get_wrapped_owner(user._id)
        self.assertTrue(isinstance(wrapped, CommCareUser))

    def test_get_wrapped_group(self):
        group = Group(domain=self.domain, name='wrapped-group-test')
        group.save()
        wrapped = get_wrapped_owner(group._id)
        self.assertTrue(isinstance(wrapped, Group))

    def test_owned_by_user(self):
        user = CommCareUser.create(self.domain, 'owned-user-test', 'password')
        user.save()
        owners = get_owning_users(user._id)
        self.assertEqual(1, len(owners))
        self.assertEqual(owners[0]._id, user._id)
        self.assertTrue(isinstance(owners[0], CommCareUser))

    def test_owned_by_group(self):
        ids = []
        for i in range(5):
            user = CommCareUser.create(self.domain, 'owned-group-test-user-%s' % i, 'password')
            user.save()
            ids.append(user._id)

        group = Group(domain=self.domain, name='owned-group-test-group', users=ids)
        group.save()
        owners = get_owning_users(group._id)
        self.assertEqual(5, len(owners))
        ids_back = []
        for o in owners:
            self.assertTrue(isinstance(o, CommCareUser))
            ids_back.append(o._id)
        self.assertEqual(set(ids), set(ids_back))
