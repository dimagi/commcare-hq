import json
from unittest import mock
from django.test import TestCase, RequestFactory
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import WebUser
from corehq.apps.users.views.mobile.users import _count_users


class UserCountTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(UserCountTest, cls).setUpClass()
        cls.domain_name = 'test-domain'
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)
        cls.addClassCleanup(cls.domain.delete)

        cls.user = WebUser.create(cls.domain_name,
                                  'test_user_',
                                  'test',
                                  None,
                                  None)
        cls.user.is_authenticated = True
        cls.addClassCleanup(cls.user.delete, cls.domain_name, deleted_by=None)

    def create_group(self):
        self.group = Group({"name": "test", "domain": self.domain_name})
        self.group.save()
        self.addClassCleanup(self.group.delete)

    def create_request(self, user_type):
        request = RequestFactory().get('/', {'user_type': user_type})
        request.user = self.user
        return request

    @mock.patch('corehq.apps.users.dbaccessors.count_mobile_users_by_filters')
    def test_count_users_mobile_worker_return_value(self, mock_count_mobile_users):
        mock_count_mobile_users.return_value = 5
        self.create_group()
        user_type = 'mobile'
        request = self.create_request(user_type)

        response = _count_users(request, self.domain_name, user_type)
        content = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(content, {'user_count': 5, 'group_count': 1})

    @mock.patch('corehq.apps.users.dbaccessors.count_web_users_by_filters')
    @mock.patch('corehq.apps.users.dbaccessors.count_invitations_by_filters')
    def test_count_users_web_user_return_value(self, mock_count_web_users, mock_count_invitations):
        mock_count_web_users.return_value = 4
        mock_count_invitations.return_value = 2
        user_type = 'web'
        request = self.create_request(user_type)

        response = _count_users(request, self.domain_name, user_type)
        content = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(content, {'user_count': 6, 'group_count': 0})
