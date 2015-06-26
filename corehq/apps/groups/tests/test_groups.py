from couchdbkit import BadValueError
from django.test import TestCase, SimpleTestCase
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser

DOMAIN = 'test-domain'


class GroupTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.active_user = CommCareUser.create(domain=DOMAIN, username='activeguy', password='secret')
        cls.inactive_user = CommCareUser.create(domain=DOMAIN, username='inactivegal', password='secret')
        cls.inactive_user.is_active = False
        cls.inactive_user.save()
        cls.deleted_user = CommCareUser.create(domain=DOMAIN, username='goner', password='secret')
        cls.deleted_user.retire()

    @classmethod
    def tearDownClass(cls):
        for group in Group.by_domain(DOMAIN):
            group.delete()
        for user in CommCareUser.all():
            user.delete()

    def testGetUsers(self):
        group = Group(domain=DOMAIN, name='group',
                      users=[self.active_user._id, self.inactive_user._id, self.deleted_user._id])
        group.save()

        def _check_active_users(userlist):
            self.assertEqual(len(userlist), 1)
            self.assertEqual(self.active_user._id, userlist[0])

        # try all the flavors of this
        _check_active_users([u._id for u in group.get_users()])
        _check_active_users(group.get_user_ids())
        _check_active_users([u._id for u in group.get_static_users()])
        _check_active_users(group.get_static_user_ids())

        def _check_all_users(userlist):
            self.assertEqual(len(userlist), 2)
            self.assertTrue(self.active_user._id in userlist)
            self.assertTrue(self.inactive_user._id in userlist)
            self.assertFalse(self.deleted_user._id in userlist)

        _check_all_users([u._id for u in group.get_users(is_active=False)])
        _check_all_users(group.get_user_ids(is_active=False))
        _check_all_users([u._id for u in group.get_static_users(is_active=False)])
        _check_all_users(group.get_static_user_ids(is_active=False))

    def test_bulk_save(self):
        group1 = Group(domain=DOMAIN, name='group1',
                       users=[self.active_user._id, self.inactive_user._id, self.deleted_user._id])
        group1.save()
        group2 = Group(domain=DOMAIN, name='group2',
                       users=[self.active_user._id, self.inactive_user._id, self.deleted_user._id])
        group2.save()

        group1.remove_user(self.active_user._id, save=False)
        group2.remove_user(self.deleted_user._id, save=False)

        g1_old_modified = group1.last_modified
        g2_old_modified = group2.last_modified

        Group.bulk_save([group1, group2])

        group1_updated = Group.get(group1.get_id)
        group2_updated = Group.get(group2.get_id)
        self.assertNotEqual(g1_old_modified, group1_updated.last_modified)
        self.assertNotEqual(g2_old_modified, group2_updated.last_modified)


# This is a mixin so importing it doesn't re-run the tests
class WrapGroupTestMixin(object):
    document_class = None

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


class WrapGroupTest(WrapGroupTestMixin, SimpleTestCase):
    document_class = Group
