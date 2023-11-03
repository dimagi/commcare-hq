import datetime

from unittest.mock import Mock

from django.test import TestCase

from corehq.apps.users.models import Invitation
from corehq.apps.users.views.web import UserInvitationView, WebUserInvitationForm

from django import forms


class StubbedWebUserInvitationForm(WebUserInvitationForm):

    def __init__(self, *args, **kwargs):
        self.request_email = kwargs.pop('request_email', False)
        super().__init__(*args, **kwargs)

    @property
    def cleaned_data(self):
        return {"email": self.request_email}


class TestUserInvitation(TestCase):

    def test_redirect_if_invite_does_not_exist(self):
        request = Mock()
        non_existing_uuid = "e1bd37f5-9ff8-4853-b953-fd75483a0ec7"
        domain = "domain"

        response = UserInvitationView()(request, non_existing_uuid, domain=domain)
        self.assertEqual(302, response.status_code)
        self.assertEqual("/accounts/login/", response.url)

    def test_redirect_if_invite_is_already_accepted(self):
        request = Mock()
        invite_uuid = "e1bd37f5-9ff8-4853-b953-fd75483a0ec7"
        domain = "domain"

        Invitation.objects.create(
            uuid=invite_uuid,
            domain=domain,
            is_accepted=True,
            invited_on=datetime.date(2023, 9, 1)
        )

        response = UserInvitationView()(request, invite_uuid, domain=domain)
        self.assertEqual(302, response.status_code)
        self.assertEqual("/accounts/login/", response.url)

    def test_redirect_if_invite_email_does_not_match(self):
        form = StubbedWebUserInvitationForm(
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

        form = WebUserInvitationForm(
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

        form = WebUserInvitationForm(
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
