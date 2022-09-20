from contextlib import contextmanager
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase
from email_validator import EmailSyntaxError

from corehq.apps.users.models import FakeUser


class TestEmailValidation(SimpleTestCase):
    """Tests the expected behavior of the management command's use of the
    `email_validator` library.
    """

    def test_make_superuser(self):
        with patch_fake_webuser():
            call_command("make_superuser", "test@dimagi.com")  # does not raise

    def test_make_superuser_rejects_special_domains(self):
        # as of email_validator 1.3.0, special domains raise EmailSyntaxError
        # see: https://github.com/JoshData/python-email-validator/blob/10c34e6/CHANGELOG.md#version-130-september-18-2022  # noqa: E501
        with (patch_fake_webuser(), self.assertRaises(CommandError) as test):
            call_command("make_superuser", "test@example.com")
        self.assertIsInstance(test.exception.__cause__, EmailSyntaxError)

    def test_make_superuser_rejects_invalid_email_syntax(self):
        with (patch_fake_webuser(), self.assertRaises(CommandError) as test):
            call_command("make_superuser", "somebody_at_dimagi.com")
        self.assertIsInstance(test.exception.__cause__, EmailSyntaxError)


@contextmanager
def patch_fake_webuser():
    with patch("corehq.apps.users.models.WebUser.get_by_username",
               side_effect=get_fake_superuser) as mock:
        yield mock


def get_fake_superuser(username):
    fake_user = FakeUser(username=username)
    # set these to True so Command.handle() doesn't call couch_user.save()
    fake_user.is_superuser = True
    fake_user.is_staff = True
    return fake_user
