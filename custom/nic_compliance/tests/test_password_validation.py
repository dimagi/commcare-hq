from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from custom.nic_compliance.password_validation import UsedPasswordValidator
from custom.nic_compliance.const import RESTRICT_USED_PASSWORDS_NUM


class TestUsedPasswordsRestriction(TestCase):
    def setUp(self):
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)
        self.username = 'auser@qwerty.commcarehq.org'
        self.password = 'apassword'
        self.user = WebUser.create(self.domain.name, self.username, self.password).get_django_user()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def test_used_password_reset(self):
        # fails for reuse of password
        with override_settings(AUTH_PASSWORD_VALIDATORS=[{
            'NAME': 'custom.nic_compliance.password_validation.UsedPasswordValidator',
        }]):
            with self.assertRaisesMessage(
                    ValidationError,
                    "Your password can not be same as last {num} passwords.".format(num=RESTRICT_USED_PASSWORDS_NUM)):
                UsedPasswordValidator().validate(self.password, self.user)
                # set as same password
                self.user._password = self.password
                self.user.save()

            # successful for a password never used
            self.user._password = "123456"
            self.user.save()

            self.user._password = "987654"
            self.user.save()

            with self.assertRaisesMessage(
                    ValidationError,
                    "Your password can not be same as last {num} passwords.".format(num=RESTRICT_USED_PASSWORDS_NUM)):
                UsedPasswordValidator().validate(self.password, self.user)
                # set as an old password
                self.user._password = "123456"
                self.user.save()

            self.user._password = "987654"
            self.user.save()

            # successful for reuse of a password used beyond restricted attempts
            self.user._password = "apassword"
            self.user.save()
