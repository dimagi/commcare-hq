from django.test import TestCase
from django.core.urlresolvers import reverse

from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.cloudcare.middleware import CloudcareMiddleware
from corehq.apps.users.models import WebUser, CommCareUser


class CloudcareMiddleware(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'cloudcare-test-views'
        cls.username = 'cornelius'
        cls.password = 'fudge'
        cls.user = WebUser.create(cls.domain, cls.username, cls.password, is_active=True)
        cls.user.is_superuser = True
        cls.user.save()

    def test_auth_as(self):
        """
        Ensures that using the URL param ?auth_as=<username> successfully
        sets the user in the cloudcare middleware
        """
        username = '{username}@{domain}.commcarehq.org'.format(
            username='muggle',
            domain=self.domain,
        )
        password = 'I solemnly swear that I am up to no good'

        muggle = CommCareUser.create(self.domain, username, password)

        self.client.login(username=self.username, password=self.password)
        resp = self.client.get(reverse('cloudcare_main', args=[self.domain, 'dummy']), {
            'auth_as': username
        })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['user'].username, username)

    def test_only_cloudcare_views(self):
        """
        Ensures that ?auth_as only affects cloudcare views
        """

    def test_permissions_for_middleware(self):
        """
        Ensures that only superusers can use ?auth_as
        """

    def test_missing_user(self):
        """
        Ensures that a proper message is given to superuser if auth_as user is not found
        """
        self.client.login(username=self.username, password=self.password)
        resp = self.client.get(reverse('cloudcare_main', args=[self.domain, 'dummy']), {
            'auth_as': 'bogus'
        })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['user'].username, self.username)
