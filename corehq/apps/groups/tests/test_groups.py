from django.test import SimpleTestCase, TestCase

from couchdbkit import BadValueError

from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.groups.dbaccessors import group_by_domain
from corehq.apps.groups.models import Group
from corehq.apps.groups.tests.test_utils import delete_all_groups
from corehq.apps.users.models import CommCareUser

DOMAIN = 'test-domain'


class GroupTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(GroupTest, cls).setUpClass()
        cls.active_user = CommCareUser.create(domain=DOMAIN, username='activeguy', password='secret',
                                              created_by=None, created_via=None)
        cls.inactive_user = CommCareUser.create(domain=DOMAIN, username='inactivegal', password='secret',
                                                created_by=None, created_via=None)
        cls.inactive_user.is_active = False
        cls.inactive_user.save()
        cls.deleted_user = CommCareUser.create(domain=DOMAIN, username='goner', password='secret',
                                               created_by=None, created_via=None)
        cls.deleted_user.retire(DOMAIN, deleted_by=None)

    def tearDown(self):
        for group in Group.by_domain(DOMAIN):
            group.delete()

    @classmethod
    def tearDownClass(cls):
        for user in CommCareUser.all():
            user.delete(DOMAIN, deleted_by=None)
        super(GroupTest, cls).tearDownClass()

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

        group1.remove_user(self.active_user._id)
        group2.remove_user(self.deleted_user._id)

        g1_old_modified = group1.last_modified
        g2_old_modified = group2.last_modified

        Group.bulk_save([group1, group2])

        group1_updated = Group.get(group1.get_id)
        group2_updated = Group.get(group2.get_id)
        self.assertNotEqual(g1_old_modified, group1_updated.last_modified)
        self.assertNotEqual(g2_old_modified, group2_updated.last_modified)

    def test_remove_user(self):
        group1 = Group(
            domain=DOMAIN,
            name='group1',
            users=[self.active_user._id, self.inactive_user._id, self.deleted_user._id]
        )
        group1.save()

        self.assertTrue(group1.remove_user(self.active_user._id))
        group1.save()

        group1 = Group.get(group1._id)
        self.assertIn(self.active_user._id, group1.removed_users)
        self.assertNotIn(self.active_user._id, group1.users)

        group1.add_user(self.active_user._id)
        group1 = Group.get(group1._id)
        self.assertNotIn(self.active_user._id, group1.removed_users)
        self.assertIn(self.active_user._id, group1.users)

    def test_set_user_ids(self):
        group = Group(
            domain=DOMAIN,
            name='group1',
            users=[self.active_user._id, self.inactive_user._id]
        )
        group.save()

        users_added_ids, users_removed_ids = group.set_user_ids([self.inactive_user._id, self.deleted_user._id])

        self.assertEqual({self.deleted_user.get_id}, users_added_ids)
        self.assertEqual({self.active_user.get_id}, users_removed_ids)
        self.assertEqual(set(group.users), {self.inactive_user._id, self.deleted_user._id})
        self.assertEqual(set(group.removed_users), {self.active_user._id})

    def test_undo_delete_group_removes_deleted_couch_doc_record(self):
        group = Group(domain=DOMAIN, name='group1')
        group.save()
        rec = group.soft_delete()
        assert group.doc_type.endswith("-Deleted")
        params = {'doc_id': rec._id, 'doc_type': rec.doc_type}
        assert DeletedCouchDoc.objects.get(**params)
        rec.undo()
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(**params)


class TestDeleteAllGroups(TestCase):

    def test_bulk_delete(self):
        domain = 'test-bulk-delete'
        for i in range(3):
            Group(domain=domain, name='group-{}'.format(i)).save()
        self.assertEqual(3, len(group_by_domain(domain)))
        delete_all_groups()
        self.assertEqual(0, len(group_by_domain(domain)))


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
