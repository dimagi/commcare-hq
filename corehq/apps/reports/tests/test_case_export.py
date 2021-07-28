from django.test import TestCase

from corehq.apps.groups.models import Group
from corehq.apps.reports.util import case_group_filter, case_users_filter
from corehq.apps.users.models import CommCareUser


def _mock_case(owner, user):
    return {
        'owner_id': owner,
        'user_id': user,
    }


class CaseExportTest(TestCase):
    domain = 'case-export-test'

    def setUp(self):
        super(CaseExportTest, self).setUp()
        for user in CommCareUser.all():
            user.delete(self.domain, deleted_by=None)

    def testUserFilters(self):
        self.assertTrue(case_users_filter(_mock_case('owner', 'user'), ['owner']))
        self.assertTrue(case_users_filter(_mock_case('owner', 'user'), ['user']))
        self.assertTrue(case_users_filter(_mock_case('owner', 'user'), ['owner', 'user']))
        self.assertTrue(case_users_filter(_mock_case('owner', 'user'), ['owner', 'user', 'rando']))
        self.assertTrue(case_users_filter(_mock_case('user', 'user'), ['user']))
        self.assertTrue(case_users_filter(_mock_case('user', 'user'), ['user', 'rando']))
        self.assertFalse(case_users_filter(_mock_case('owner', 'user'), []))
        self.assertFalse(case_users_filter(_mock_case('owner', 'user'), ['rando']))
        self.assertFalse(case_users_filter(_mock_case('owner', 'user'), ['rando', 'stranger', 'ghost']))

    def testGroupFilters(self):
        active_user = CommCareUser.create(domain=self.domain, username='activeguy', password='secret',
                                          created_by=None, created_via=None)
        inactive_user = CommCareUser.create(domain=self.domain, username='inactivegal', password='secret',
                                            created_by=None, created_via=None)
        inactive_user.is_active = False
        inactive_user.save()

        group = Group(domain=self.domain, name='group', users=[active_user._id, inactive_user._id])
        group.save()

        # no matter what the group should match on ownerid (but not user id)
        self.assertTrue(case_group_filter(_mock_case(group._id, 'nobody'), group))
        self.assertTrue(case_group_filter(_mock_case(group._id, active_user._id), group))
        self.assertTrue(case_group_filter(_mock_case(group._id, inactive_user._id), group))
        self.assertFalse(case_group_filter(_mock_case('nobody', group._id), group))

        # test active users count
        self.assertTrue(case_group_filter(_mock_case(active_user._id, 'nobody'), group))
        self.assertTrue(case_group_filter(_mock_case('nobody', active_user._id), group))
        self.assertTrue(case_group_filter(_mock_case(active_user._id, active_user._id), group))

        # test inactive users don't count
        self.assertFalse(case_group_filter(_mock_case(inactive_user._id, 'nobody'), group))
        self.assertFalse(case_group_filter(_mock_case('nobody', inactive_user._id), group))
        self.assertFalse(case_group_filter(_mock_case(inactive_user._id, inactive_user._id), group))

        # combinations of active and inactive should count
        self.assertTrue(case_group_filter(_mock_case(active_user._id, inactive_user._id), group))
        self.assertTrue(case_group_filter(_mock_case(inactive_user._id, active_user._id), group))

        # duh
        self.assertFalse(case_group_filter(_mock_case('nobody', 'nobody-else'), group))
