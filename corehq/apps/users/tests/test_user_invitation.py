import datetime

from unittest.mock import Mock, patch

from corehq.apps.users.models import Invitation, WebUser
from corehq.apps.users.views.web import UserInvitationView, AcceptedWebUserInvitationForm

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models_role import UserRole


class InvitationTestException(Exception):
    pass


class StubbedAcceptedWebUserInvitationForm(AcceptedWebUserInvitationForm):

    def __init__(self, *args, **kwargs):
        self.request_email = kwargs.pop('request_email', False)
        super().__init__(*args, **kwargs)

    @property
    def cleaned_data(self):
        return {"email": self.request_email}


class TestUserInvitation(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.domain = "domain"
        cls.factory = RequestFactory()
        cls.project = bootstrap_domain(cls.domain)
        cls.role1 = UserRole.objects.create(
            domain=cls.domain,
            name="role1"
        )

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        delete_all_users()
        return super().tearDownClass()

    def tearDown(cls):
        delete_all_users()
        return super().tearDown()

    def test_redirect_if_invite_does_not_exist(self):
        request = Mock()
        non_existing_uuid = "e1bd37f5-9ff8-4853-b953-fd75483a0ec7"

        response = UserInvitationView()(request, non_existing_uuid, domain=self.domain)
        self.assertEqual(302, response.status_code)
        self.assertEqual("/accounts/login/", response.url)

    def test_redirect_if_invite_is_already_accepted(self):
        request = Mock()
        invite_uuid = "e1bd37f5-9ff8-4853-b953-fd75483a0ec7"

        Invitation.objects.create(
            email='test@dimagi.com',
            uuid=invite_uuid,
            domain=self.domain,
            is_accepted=True,
            invited_on=datetime.date(2023, 9, 1),
            invited_by="system@dimagi.com",
        )

        response = UserInvitationView()(request, invite_uuid, domain=self.domain)
        self.assertEqual(302, response.status_code)
        self.assertEqual("/accounts/login/", response.url)

    def test_redirect_if_invite_email_does_not_match(self):
        form = StubbedAcceptedWebUserInvitationForm(
            {
                "email": "other_test@dimagi.com",
                "full_name": "asdf",
                "password": "pass",
            },
            is_sso=False,
            allow_invite_email_only=True,
            invite_email="test@dimagi.com",
            request_email="other_test@dimagi.com",
        )

        with self.assertRaises(forms.ValidationError) as ve:
            form.clean_email()

        self.assertEqual(
            str(ve.exception),
            "['You can only sign up with the email address your invitation was sent to.']")

        form = AcceptedWebUserInvitationForm(
            {
                "email": "other_test@dimagi.com",
                "full_name": "asdf",
                "password": "pass12342&*LKJ",
                "eula_confirmed": True
            },
            is_sso=False,
            allow_invite_email_only=False,
            invite_email="test@dimagi.com",
        )

        print(form.errors)
        self.assertTrue(form.is_valid())

        form = AcceptedWebUserInvitationForm(
            {
                "email": "test@dimagi.com",
                "full_name": "asdf",
                "password": "pass12342&*LKJ",
                "eula_confirmed": True
            },
            is_sso=False,
            allow_invite_email_only=True,
            invite_email="test@dimagi.com",
        )

        self.assertTrue(form.is_valid())

    def _setup_invitation_and_request(self):
        invite_uuid = "e1bd37f5-9ff8-4853-b953-fd75483a0ec7"
        request = self.factory.post(f"/join/{invite_uuid}")
        request.user = AnonymousUser()
        request.POST = {
            "email": "test5@dimagi.com",
            "full_name": "Testy Tester",
            "password": "pass12342&*LKJ",
            "eula_confirmed": True
        }
        Invitation.objects.create(
            email='test5@dimagi.com',
            uuid=invite_uuid,
            domain=self.domain,
            is_accepted=False,
            invited_on=(datetime.datetime.now() - datetime.timedelta(days=1)),
            invited_by="system@dimagi.com",
            role=self.role1.get_qualified_id()
        )
        return request, invite_uuid

    @patch('corehq.apps.users.models.Invitation._send_confirmation_email')
    @patch('corehq.apps.users.views.web.login')
    @patch('corehq.apps.users.views.web.messages')
    def test_successful_accept_invite_and_user_created(self, mock_messages, mock_login,
                                                       mock_confirmation_email):
        self.assertIsNone(WebUser.get_by_username('test5@dimagi.com'))
        request, invite_uuid = self._setup_invitation_and_request()
        response = UserInvitationView()(request, invite_uuid, domain=self.domain)
        self.assertEqual(302, response.status_code)
        self.assertTrue(WebUser.get_by_username('test5@dimagi.com'))

    @patch('corehq.apps.users.models.Invitation._send_confirmation_email')
    @patch('corehq.apps.users.views.web.login')
    @patch('corehq.apps.users.views.web.messages')
    @patch('corehq.apps.users.models.Invitation.accept_invitation_and_join_domain')
    def test_atomic_user_invite(self, accept_invitation_mock, mock_messages, mock_login,
                                mock_confirmation_email):
        accept_invitation_mock.side_effect = Mock(side_effect=InvitationTestException())
        request, invite_uuid = self._setup_invitation_and_request()
        with self.assertRaises(InvitationTestException):
            response = UserInvitationView()(request, invite_uuid, domain=self.domain)
            self.assertEqual(400, response.status_code)
        self.assertIsNone(WebUser.get_by_username('test5@dimagi.com'))
