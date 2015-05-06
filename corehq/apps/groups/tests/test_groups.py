from couchdbkit import BadValueError
from django.test import TestCase, SimpleTestCase
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


class WrapGroupTest(SimpleTestCase):

    document_class = Group

    def test_yes_Z(self):
        date_string = '2014-08-26T15:20:20.062732Z'
        group = self.document_class.wrap({'last_modified': date_string})
        self.assertEqual(group.to_json()['last_modified'], date_string)
        date_string_no_usec = '2014-08-26T15:20:20Z'
        date_string_yes_usec = '2014-08-26T15:20:20.000000Z'
        group = self.document_class.wrap({'last_modified': date_string_no_usec})
        self.assertEqual(group.to_json()['last_modified'], date_string_yes_usec)

    def test_no_Z(self):
        date_string_no_Z = '2014-08-26T15:20:20.062732'
        date_string_yes_Z = '2014-08-26T15:20:20.062732Z'
        group = self.document_class.wrap({'last_modified': date_string_no_Z})
        self.assertEqual(group.to_json()['last_modified'], date_string_yes_Z)
        # iso_format can, technically, produce this if microseconds
        # happens to be exactly 0
        date_string_no_Z = '2014-08-26T15:20:20'
        date_string_yes_Z = '2014-08-26T15:20:20.000000Z'
        group = self.document_class.wrap({'last_modified': date_string_no_Z})
        self.assertEqual(group.to_json()['last_modified'], date_string_yes_Z)

    def test_fail(self):
        bad_date_string = '2014-08-26T15:20'
        with self.assertRaises(BadValueError):
            self.document_class.wrap({'last_modified': bad_date_string})
