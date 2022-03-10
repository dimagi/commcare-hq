from unittest import mock

from django.http import Http404
from django.test import TestCase, RequestFactory

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.accounting.tests import generator
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.decorators import require_enterprise_admin
from corehq.apps.users.models import WebUser


class TestRequireEnterpriseAdminDecorator(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain(
            name="test-enterprise-001",
            is_active=True
        )
        cls.domain.save()
        cls.enterprise_admin = WebUser.create(
            cls.domain.name, generator.create_arbitrary_web_user_name(),
            'testpwd', None, None
        )
        cls.other_domain_user = WebUser.create(
            cls.domain.name, generator.create_arbitrary_web_user_name(),
            'testpwd', None, None
        )
        cls.account = BillingAccount.get_or_create_account_by_domain(
            cls.domain.name, created_by=cls.enterprise_admin.username
        )[0]
        cls.account.is_customer_billing_account = True
        cls.account.enterprise_admin_emails = [cls.enterprise_admin.username]
        cls.account.save()

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/enterprise/dashboard')
        self.request_args = (self.domain.name, )
        self.view = mock.MagicMock(return_value='fake response')

    def test_request_succeeds_for_enterprise_admin(self):
        self.request.couch_user = self.enterprise_admin
        decorated_view = require_enterprise_admin(self.view)
        decorated_view(self.request, *self.request_args)

        self.view.assert_called_once_with(self.request, *self.request_args)
        self.assertEqual(self.request.account, self.account)

    def test_request_fails_for_unauthorized_user(self):
        self.request.couch_user = self.other_domain_user
        decorated_view = require_enterprise_admin(self.view)
        with self.assertRaises(Http404):
            decorated_view(self.request, *self.request_args)

    @classmethod
    def tearDownClass(cls):
        cls.enterprise_admin.delete(cls.domain.name, deleted_by=None)
        cls.other_domain_user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        cls.account.delete()
        super().tearDownClass()
