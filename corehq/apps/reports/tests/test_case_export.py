from django.test import TestCase

from corehq.apps.groups.models import Group
from corehq.apps.reports.util import case_users_filter
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
