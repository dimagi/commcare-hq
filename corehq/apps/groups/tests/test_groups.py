from django.test import TestCase
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser

class GroupTest(TestCase):

    def setUp(self):
        for user in CommCareUser.all():
            user.delete()

    def testGetUsers(self):
        domain = 'group-test'
        active_user = CommCareUser.create(domain=domain, username='activeguy', password='secret')
        inactive_user = CommCareUser.create(domain=domain, username='inactivegal', password='secret')
        inactive_user.is_active = False
        inactive_user.save()
        deleted_user = CommCareUser.create(domain=domain, username='goner', password='secret')
        deleted_user.retire()

        group = Group(domain=domain, name='group',
                      users=[active_user._id, inactive_user._id, deleted_user._id])
        group.save()

        def _check_active_users(userlist):
            self.assertEqual(len(userlist), 1)
            self.assertEqual(active_user._id, userlist[0])

        # try all the flavors of this
        _check_active_users([u._id for u in group.get_users()])
        _check_active_users(group.get_user_ids())
        _check_active_users([u._id for u in group.get_static_users()])
        _check_active_users(group.get_static_user_ids())

        def _check_all_users(userlist):
            self.assertEqual(len(userlist), 2)
            self.assertTrue(active_user._id in userlist)
            self.assertTrue(inactive_user._id in userlist)
            self.assertFalse(deleted_user._id in userlist)

        _check_all_users([u._id for u in group.get_users(is_active=False)])
        _check_all_users(group.get_user_ids(is_active=False))
        _check_all_users([u._id for u in group.get_static_users(is_active=False)])
        _check_all_users(group.get_static_user_ids(is_active=False))


