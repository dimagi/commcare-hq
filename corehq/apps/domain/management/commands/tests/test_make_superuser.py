from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.core.validators import ValidationError
from django.test import SimpleTestCase

from corehq.apps.users.models import FakeUser


class TestEmailValidation(SimpleTestCase):
    """Tests the expected behavior of the management command's use of the
    `email_validator` library.
    """

    def test_make_superuser(self):
        with patch_fake_webuser():
            call_command("make_superuser", "test@dimagi.com")  # does not raise

    def test_make_superuser_allows_special_domains(self):
        # as-built with email_validator version 1.1.3
        with patch_fake_webuser():
            call_command("make_superuser", "test@example.com")  # does not raise

    def test_make_superuser_rejects_invalid_email_syntax(self):
        with patch_fake_webuser(), self.assertRaises(CommandError) as test:
            call_command("make_superuser", "somebody_at_dimagi.com")
        self.assertIsInstance(test.exception.__cause__, ValidationError)


def patch_fake_webuser():
    return patch("corehq.apps.users.models.WebUser.get_by_username",
                 side_effect=get_fake_superuser)


def get_fake_superuser(username):
    fake_user = FakeUser(username=username)
    # set these to True so Command.handle() doesn't call couch_user.save()
    fake_user.is_superuser = True
    fake_user.is_staff = True
    fake_user.can_assign_superuser = True
    return fake_user
