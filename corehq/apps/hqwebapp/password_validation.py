from django.contrib.auth.hashers import get_hasher
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from corehq.apps.hqwebapp.const import ALLOWED_OLD_PASSWORDS
from corehq.apps.hqwebapp.models import UsedPasswords


class ReusedPasswordValidator(object):
    def validate(self, password, user=None):
        hasher = get_hasher()
        used_passwords = UsedPasswords.objects.filter(
            user=user,
        ).order_by('-created_at').all()[:ALLOWED_OLD_PASSWORDS - 1].values_list('password', flat=True)
        used_passwords = list(used_passwords) + [user.password]
        for used_password in used_passwords:
            if hasher.verify(password, used_password):
                raise ValidationError(
                    _("Your password can not be same as earlier {allowed} passwords.").format(
                        allowed=ALLOWED_OLD_PASSWORDS
                    ),
                    code='password_already_user',
                )

    def password_changed(self, password, user):
        hasher = get_hasher()
        UsedPasswords.objects.create(
            user=user,
            password=hasher.encode(password, hasher.salt())
        )

    def get_help_text(self):
        return _("Your password can't be same as earlier {allowed} passwords.").format(
            allowed=ALLOWED_OLD_PASSWORDS
        )
