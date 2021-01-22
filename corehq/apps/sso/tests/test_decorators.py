from unittest import mock

from django.test import TestCase, RequestFactory

from corehq.apps.sso.decorators import (
    identity_provider_required,
    use_saml2_auth,
)
from corehq.apps.sso.tests import generator


class TestDecorators(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()

    def setUp(self):
        super().setUp()
        self.idp = generator.create_idp(self.account, include_certs=True)

        self.request = RequestFactory().get('/sso/test')
        self.request_args = (self.idp.slug, )
        self.view = mock.MagicMock(return_value='fake response')

    def test_identity_provider_required_decorator(self):
        decorated_view = identity_provider_required(self.view)
        decorated_view(self.request, *self.request_args)

        self.view.assert_called_once_with(self.request, *self.request_args)
        self.assertEqual(self.request.idp, self.idp)

    def test_use_saml2_auth_decorator(self):
        decorated_view = use_saml2_auth(self.view)
        decorated_view(self.request, *self.request_args)

        self.view.assert_called_once_with(self.request, *self.request_args)
        self.assertEqual(self.request.idp, self.idp)
        self.assertIsNotNone(self.request.saml2_auth)

    def tearDown(self):
        self.idp.delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.account.delete()
        super().tearDownClass()
